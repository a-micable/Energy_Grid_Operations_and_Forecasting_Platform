from __future__ import annotations

from decimal import Decimal

import pytest

from gridmind.core.exceptions import ConflictError
from gridmind.domains.grid.service import GridZoneService


@pytest.mark.asyncio
async def test_create_zone_and_resources(db_session) -> None:
    svc = GridZoneService(db_session)
    zone = await svc.create_zone("TEST-01", "Test Zone", "Test", Decimal("1000"))
    resource = await svc.register_resource(
        zone.id, "TEST-GAS-01", "Test Gas", "gas_plant",
        Decimal("200"), Decimal("50"),
    )
    assert resource.zone_id == zone.id
    summary = await svc.get_zone_capacity_summary(zone.id)
    assert summary["total_capacity_mw"] == 200.0


@pytest.mark.asyncio
async def test_duplicate_zone_code_rejected(db_session) -> None:
    svc = GridZoneService(db_session)
    await svc.create_zone("DUP-01", "Zone A", "Test", Decimal("1000"))
    with pytest.raises(ConflictError):
        await svc.create_zone("DUP-01", "Zone B", "Test", Decimal("2000"))
