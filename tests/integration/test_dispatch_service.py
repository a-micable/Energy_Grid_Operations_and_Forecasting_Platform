from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from gridmind.domains.dispatch.optimizer import ResourceOffer
from gridmind.domains.dispatch.service import DispatchService


@pytest.mark.asyncio
async def test_create_dispatch_plan(db_session, sample_zone, sample_resources) -> None:
    service = DispatchService(db_session)
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=1)
    resources = [
        ResourceOffer(
            resource_id=r.id,
            resource_type=r.resource_type,
            min_output_mw=r.min_output_mw,
            max_output_mw=r.capacity_mw,
            marginal_cost=r.marginal_cost_per_mwh,
            emission_rate=r.emission_rate_kg_co2_per_mwh,
            dispatch_priority=r.dispatch_priority,
            ramp_rate_mw_per_min=r.ramp_rate_mw_per_min,
        )
        for r in sample_resources
    ]
    plan, result = await service.create_dispatch_plan(
        sample_zone.id,
        Decimal("400"),
        resources,
        start,
        end,
        created_by="dispatcher@grid.com",
    )
    assert plan.status == "scheduled"
    assert result.total_output_mw >= Decimal("400")
    assert plan.total_cost is not None
