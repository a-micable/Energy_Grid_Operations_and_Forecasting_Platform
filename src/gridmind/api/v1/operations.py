from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.api.deps import get_session
from gridmind.db.queries.operational import OperationalQueries
from gridmind.domains.analytics.reporting import OperationalReportGenerator
from gridmind.domains.analytics.historical import TimeSeriesPoint
from gridmind.domains.operations.decision_support import OperationalDecisionSupport
from gridmind.domains.operations.playbooks import PlaybookRegistry
from gridmind.domains.simulation.scenario_runner import ScenarioSimulator, ScenarioType, SimulationConfig
from gridmind.notifications.alerting import AlertManager
from gridmind.services.coordinator import OperationalCoordinator

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/zones/{zone_id}/summary")
async def get_zone_summary(zone_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    queries = OperationalQueries(session)
    return await queries.get_zone_operational_summary(zone_id)


@router.get("/zones/{zone_id}/forecast-accuracy")
async def get_forecast_accuracy(
    zone_id: UUID,
    session: AsyncSession = Depends(get_session),
    days: int = Query(default=7, le=90),
) -> list[dict]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    queries = OperationalQueries(session)
    return await queries.get_forecast_accuracy_by_type(zone_id, start, end)


@router.get("/zones/{zone_id}/upcoming-outages")
async def get_upcoming_outages(
    zone_id: UUID,
    session: AsyncSession = Depends(get_session),
    days: int = Query(default=30, le=180),
) -> list[dict]:
    queries = OperationalQueries(session)
    return await queries.get_upcoming_outages(zone_id, days)


@router.post("/simulation/run")
async def run_simulation(
    zone_id: UUID,
    scenario_type: ScenarioType = ScenarioType.NORMAL,
    duration_hours: int = Query(default=24, le=168),
    base_demand_mw: float = 2000.0,
) -> dict:
    simulator = ScenarioSimulator()
    config = SimulationConfig(
        scenario_type=scenario_type,
        zone_id=zone_id,
        duration_hours=duration_hours,
        base_demand_mw=base_demand_mw,
    )
    result = simulator.run(config)
    return {"simulation_id": str(result.simulation_id), "summary": result.summary, "warnings": result.warnings}


@router.get("/playbooks")
async def list_playbooks() -> list[dict]:
    registry = PlaybookRegistry()
    return [
        {"id": p.playbook_id, "name": p.name, "category": p.category.value, "severity": p.severity.value}
        for p in registry.list_playbooks()
    ]


@router.get("/alerts/active")
async def get_active_alerts() -> list[dict]:
    manager = AlertManager()
    return [
        {
            "id": str(a.alert_id),
            "title": a.title,
            "severity": a.severity.value,
            "message": a.message,
            "created_at": a.created_at.isoformat(),
        }
        for a in manager.get_active_alerts()
    ]
