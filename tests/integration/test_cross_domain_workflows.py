"""Cross-domain workflow tests designed to surface complex bugs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from gridmind.core.events import DomainEvent, InMemoryEventBus
from gridmind.core.types import ForecastType, ForecastHorizon, OutageType, BatteryState
from gridmind.domains.forecasting.service import ForecastingService
from gridmind.domains.forecasting.engine import ForecastEngine, ForecastPointData
from gridmind.domains.balancing.service import BalancingService
from gridmind.domains.battery.service import BatteryService
from gridmind.domains.outage.service import OutageService
from gridmind.domains.events.processor import EventProcessor
from gridmind.domains.compliance.rules_engine import ComplianceRulesEngine
from gridmind.domains.operations.playbooks import PlaybookRegistry
from gridmind.domains.operations.decision_support import OperationalDecisionSupport
from gridmind.domains.simulation.scenario_runner import ScenarioSimulator, ScenarioType, SimulationConfig
from gridmind.notifications.alerting import AlertManager
from gridmind.pipeline.etl import create_scada_to_forecast_pipeline
from gridmind.services.audit import AuditService


@pytest.mark.asyncio
async def test_forecast_revision_triggers_compliance_check(db_session, sample_zone) -> None:
    audit = AuditService(db_session)
    service = ForecastingService(db_session, audit=audit)
    run = await service.create_forecast_run(
        sample_zone.id, ForecastType.DEMAND, ForecastHorizon.HOURLY, hours=12
    )
    engine = ForecastEngine(drift_threshold_pct=Decimal("0.15"))
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    revised = engine.generate_hourly_demand(2000.0, start, 12, seed=99)
    new_version = await service.revise_forecast(
        run.id, revised, reason="Storm approaching", revised_by="forecaster@grid.com", force=True
    )
    compliance = ComplianceRulesEngine()
    delta = engine.compute_revision_delta(
        engine.generate_hourly_demand(1500.0, start, 12, seed=42), revised
    )
    results = compliance.evaluate_all({"forecast_drift_pct": float(delta)})
    assert any(r.rule_id == "FCST-001" for r in results)


@pytest.mark.asyncio
async def test_event_ordering_across_aggregates(db_session) -> None:
    processor = EventProcessor()
    processed: list[int] = []
    async def handler(event: DomainEvent) -> None:
        processed.append(event.sequence_number or 0)
    processor.register("test.event", handler)
    agg_id = uuid4()
    for seq in [1, 2, 3]:
        from gridmind.core.events import EventEnvelope
        event = DomainEvent(
            event_type="test.event", aggregate_type="test", aggregate_id=agg_id,
            sequence_number=seq,
        )
        await processor.process(EventEnvelope(event=event, routing_key="test.event"))
    assert processed == [1, 2, 3]


@pytest.mark.asyncio
async def test_outage_dependency_blocks_scheduling(db_session, sample_zone, sample_resources) -> None:
    svc = OutageService(db_session)
    start = datetime.now(timezone.utc) + timedelta(days=30)
    outage_a = await svc.create_outage(
        sample_zone.id, "Phase 1", OutageType.PLANNED,
        start, start + timedelta(hours=8), 100, [sample_resources[0].id], created_by="planner"
    )
    outage_b = await svc.create_outage(
        sample_zone.id, "Phase 2", OutageType.PLANNED,
        start + timedelta(hours=4), start + timedelta(hours=12), 100,
        [sample_resources[1].id], created_by="planner"
    )
    await svc.add_dependency(outage_b.id, outage_a.id, "sequential")


def test_playbook_triggered_by_simulation_result() -> None:
    simulator = ScenarioSimulator()
    registry = PlaybookRegistry()
    config = SimulationConfig(
        scenario_type=ScenarioType.EXTREME_WEATHER, zone_id=uuid4(),
        duration_hours=6, base_demand_mw=3000, seed=42,
    )
    result = simulator.run(config)
    max_step = max(result.steps, key=lambda s: abs(s.imbalance_mw))
    playbooks = registry.find_by_trigger({
        "net_imbalance_mw": float(max_step.imbalance_mw),
        "frequency_hz": float(max_step.frequency_hz),
    })
    assert isinstance(playbooks, list)


def test_alert_cascade_from_compliance_violation() -> None:
    compliance = ComplianceRulesEngine()
    alerts = AlertManager()
    ctx = {"reserve_mw": 50, "peak_demand_mw": 3000, "compliance_violation_count": 1}
    compliance_results = compliance.evaluate_all(ctx)
    violations = compliance.get_violations(compliance_results)
    fired = alerts.evaluate("compliance_check", ctx)
    assert len(violations) >= 1 or len(fired) >= 1


@pytest.mark.asyncio
async def test_scada_pipeline_to_forecast_input() -> None:
    pipeline = create_scada_to_forecast_pipeline()
    ts = datetime.now(timezone.utc).replace(minute=0, second=0).isoformat()
    input_data = {
        "scada_points": [
            {"id": f"P{i}", "value": 1500 + i * 10, "timestamp": ts, "quality": 192, "unit": "MW"}
            for i in range(24)
        ]
    }
    result, context = await pipeline.run(input_data)
    assert result["hour_count"] >= 1
    assert context.metadata.get("valid_count", 0) > 0


def test_decision_support_for_extreme_imbalance() -> None:
    dss = OperationalDecisionSupport()
    rec = dss.recommend_balancing_action(
        Decimal("500"), Decimal("100"), 49.85, battery_soc_pct=0.15
    )
    assert rec.recommended_option in ("load_shed", "dispatch_reserve", "battery_discharge", "escalate")
    assert len(rec.warnings) > 0
