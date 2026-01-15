from __future__ import annotations

from uuid import uuid4

import pytest

from gridmind.services.coordinator import OperationalCoordinator


@pytest.mark.asyncio
async def test_daily_operations_cycle(db_session, sample_zone, sample_resources) -> None:
    coordinator = OperationalCoordinator(db_session)
    resources = [
        {
            "id": r.id,
            "type": r.resource_type,
            "min_mw": float(r.min_output_mw),
            "max_mw": float(r.capacity_mw),
            "cost": float(r.marginal_cost_per_mwh),
            "emissions": float(r.emission_rate_kg_co2_per_mwh),
            "priority": r.dispatch_priority,
        }
        for r in sample_resources
    ]
    result = await coordinator.run_daily_operations_cycle(
        sample_zone.id, resources, base_demand_mw=400.0
    )
    assert "forecast" in result["steps"]
    assert "dispatch" in result["steps"]
    assert "balancing" in result["steps"]
    assert "compliance" in result["steps"]
