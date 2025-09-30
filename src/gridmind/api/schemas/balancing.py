from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from gridmind.api.schemas.common import GridMindSchema, TimestampMixin, UUIDMixin
from gridmind.core.types import BalancingMode


class RecordSnapshotRequest(GridMindSchema):
    zone_id: UUID
    supply_mw: Decimal
    demand_mw: Decimal
    reserve_mw: Decimal
    mode: BalancingMode = BalancingMode.REALTIME
    frequency_hz: Decimal | None = None


class BalancingSnapshotResponse(UUIDMixin, TimestampMixin):
    zone_id: UUID
    snapshot_at: datetime
    supply_mw: Decimal
    demand_mw: Decimal
    net_imbalance_mw: Decimal
    frequency_hz: Decimal
    mode: str
    reserve_available_mw: Decimal


class ExecuteBalancingRequest(GridMindSchema):
    zone_id: UUID
    mode: BalancingMode = BalancingMode.REALTIME
    actor: str = "api"
