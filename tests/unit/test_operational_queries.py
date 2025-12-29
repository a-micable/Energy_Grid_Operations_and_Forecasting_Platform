from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from gridmind.db.models.balancing import BalancingSnapshot
from gridmind.db.queries.operational import OperationalQueries


@pytest.mark.asyncio
async def test_zone_operational_summary(db_session, sample_zone, sample_resources) -> None:
    snapshot = BalancingSnapshot(
        zone_id=sample_zone.id,
        snapshot_at=datetime.now(timezone.utc),
        supply_mw=Decimal("1000"),
        demand_mw=Decimal("1050"),
        net_imbalance_mw=Decimal("-50"),
        frequency_hz=Decimal("49.98"),
        mode="realtime",
        reserve_available_mw=Decimal("200"),
    )
    db_session.add(snapshot)
    await db_session.flush()
    queries = OperationalQueries(db_session)
    summary = await queries.get_zone_operational_summary(sample_zone.id)
    assert summary["zone_code"] == sample_zone.code
    assert summary["resource_count"] == len(sample_resources)
    assert summary["latest_imbalance_mw"] == -50.0


@pytest.mark.asyncio
async def test_renewable_penetration_empty(db_session, sample_zone) -> None:
    queries = OperationalQueries(db_session)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 1, 31, tzinfo=timezone.utc)
    result = await queries.get_renewable_penetration(sample_zone.id, start, end)
    assert result["renewable_pct"] == 0
