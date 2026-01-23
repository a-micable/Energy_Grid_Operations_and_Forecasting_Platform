"""End-to-end operational scenario tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from gridmind.core.types import BalancingMode, ForecastHorizon, ForecastType, OutageType
from gridmind.domains.balancing.service import BalancingService
from gridmind.domains.dispatch.optimizer import DispatchOptimizer, ResourceOffer
from gridmind.domains.forecasting.service import ForecastingService
from gridmind.domains.outage.service import OutageService
from tests.fixtures.grid_data import OPERATIONAL_SCENARIOS


@pytest.mark.asyncio
async def test_summer_peak_scenario(db_session, sample_zone, sample_resources) -> None:
    scenario = OPERATIONAL_SCENARIOS["summer_peak"]
    forecast_svc = ForecastingService(db_session)
    run = await forecast_svc.create_forecast_run(
        sample_zone.id, ForecastType.DEMAND, ForecastHorizon.HOURLY,
        base_load_mw=scenario["demand_mw"], hours=24,
    )
    assert run.status == "completed"

    balancing_svc = BalancingService(db_session)
    supply = Decimal(str(scenario["demand_mw"] * (1 - scenario["renewable_pct"])))
    demand = Decimal(str(scenario["demand_mw"]))
    reserve = demand * Decimal(str(scenario["reserve_margin"]))
    snapshot = await balancing_svc.record_snapshot(
        sample_zone.id, supply, demand, reserve, mode=BalancingMode.REALTIME,
    )
    assert snapshot.net_imbalance_mw == supply - demand


@pytest.mark.asyncio
async def test_emergency_outage_scenario(db_session, sample_zone, sample_resources) -> None:
    outage_svc = OutageService(db_session)
    start = datetime.now(timezone.utc) + timedelta(days=7)
    end = start + timedelta(hours=8)
    outage = await outage_svc.create_outage(
        sample_zone.id,
        "Emergency Gas Plant Outage",
        OutageType.EMERGENCY,
        start, end,
        impact_mw=500.0,
        resource_ids=[sample_resources[0].id],
        created_by="operator@grid.com",
    )
    assert outage.status == "draft"
    assert outage.outage_type == "emergency"


@pytest.mark.asyncio
async def test_dispatch_under_emission_constraint(db_session, sample_zone, sample_resources) -> None:
    optimizer = DispatchOptimizer(max_emissions_kg=Decimal("50000"))
    resources = [
        ResourceOffer(
            resource_id=r.id, resource_type=r.resource_type,
            min_output_mw=r.min_output_mw, max_output_mw=r.capacity_mw,
            marginal_cost=r.marginal_cost_per_mwh,
            emission_rate=r.emission_rate_kg_co2_per_mwh,
            dispatch_priority=r.dispatch_priority,
            ramp_rate_mw_per_min=r.ramp_rate_mw_per_min,
        )
        for r in sample_resources
    ]
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=1)
    result = optimizer.optimize(Decimal("400"), resources, start, end)
    assert result.total_output_mw > 0
