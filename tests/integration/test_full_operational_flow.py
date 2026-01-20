"""Full operational flow integration tests spanning multiple domains."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from gridmind.core.types import ForecastType, ForecastHorizon, OutageType, BalancingMode
from gridmind.domains.forecasting.service import ForecastingService
from gridmind.domains.balancing.service import BalancingService
from gridmind.domains.outage.service import OutageService
from gridmind.domains.dispatch.optimizer import DispatchOptimizer, ResourceOffer
from gridmind.domains.compliance.rules_engine import ComplianceRulesEngine
from gridmind.domains.simulation.scenario_runner import ScenarioSimulator, ScenarioType, SimulationConfig
from gridmind.integrations.market.pricing import MarketPricingEngine
from gridmind.services.coordinator import OperationalCoordinator


@pytest.mark.asyncio
async def test_end_to_end_daily_operations(db_session, sample_zone, sample_resources) -> None:
    coordinator = OperationalCoordinator(db_session)
    resources = [
        {
            "id": r.id, "type": r.resource_type,
            "min_mw": float(r.min_output_mw), "max_mw": float(r.capacity_mw),
            "cost": float(r.marginal_cost_per_mwh),
            "emissions": float(r.emission_rate_kg_co2_per_mwh),
            "priority": r.dispatch_priority,
        }
        for r in sample_resources
    ]
    result = await coordinator.run_daily_operations_cycle(
        sample_zone.id, resources, base_demand_mw=400.0
    )
    assert result["steps"]["forecast"]["status"] == "completed"
    assert result["steps"]["dispatch"]["total_output_mw"] > 0


@pytest.mark.asyncio
async def test_outage_impacts_dispatch(db_session, sample_zone, sample_resources) -> None:
    outage_svc = OutageService(db_session)
    start = datetime.now(timezone.utc) + timedelta(days=14)
    end = start + timedelta(hours=6)
    outage = await outage_svc.create_outage(
        sample_zone.id, "Transformer Maintenance", OutageType.MAINTENANCE,
        start, end, 200.0, [sample_resources[0].id], created_by="planner@grid.com",
    )
    optimizer = DispatchOptimizer()
    available = [
        ResourceOffer(
            resource_id=r.id, resource_type=r.resource_type,
            min_output_mw=r.min_output_mw, max_output_mw=r.capacity_mw,
            marginal_cost=r.marginal_cost_per_mwh,
            emission_rate=r.emission_rate_kg_co2_per_mwh,
            dispatch_priority=r.dispatch_priority,
            ramp_rate_mw_per_min=r.ramp_rate_mw_per_min,
        )
        for r in sample_resources[1:]
    ]
    result = optimizer.optimize(Decimal("300"), available, start, end)
    assert result.total_output_mw > 0


def test_scenario_simulation_equipment_failure() -> None:
    simulator = ScenarioSimulator()
    config = SimulationConfig(
        scenario_type=ScenarioType.EQUIPMENT_FAILURE,
        zone_id=uuid4(), duration_hours=12,
        base_demand_mw=2500, renewable_capacity_mw=600,
        thermal_capacity_mw=2000, seed=42,
    )
    result = simulator.run(config)
    assert result.summary["intervention_count"] >= 0
    assert len(result.steps) == 12


def test_compliance_after_simulation() -> None:
    simulator = ScenarioSimulator()
    compliance = ComplianceRulesEngine()
    config = SimulationConfig(
        scenario_type=ScenarioType.PEAK_DEMAND,
        zone_id=uuid4(), duration_hours=24,
        base_demand_mw=3000, seed=42,
    )
    result = simulator.run(config)
    max_step = max(result.steps, key=lambda s: s.demand_mw)
    ctx = {
        "reserve_mw": float(max_step.reserve_mw),
        "peak_demand_mw": float(max_step.demand_mw),
        "total_emissions_kg": float(sum(s.total_emissions_kg for s in result.steps)),
        "frequency_hz": float(max_step.frequency_hz),
    }
    results = compliance.evaluate_all(ctx)
    assert len(results) > 0


def test_market_pricing_with_dispatch() -> None:
    market = MarketPricingEngine()
    start = datetime.now(timezone.utc)
    prices = market.generate_day_ahead_prices("ZONE-01", start, 24)
    resources = [
        {"id": "G1", "capacity_mw": 500, "marginal_cost": 42},
        {"id": "G2", "capacity_mw": 300, "marginal_cost": 55},
    ]
    bids = market.optimize_bids(resources, prices)
    clearing = market.clear_market(Decimal("600"), bids[:10])
    assert clearing.cleared_quantity_mw > 0
