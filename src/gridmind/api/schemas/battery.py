from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from gridmind.api.schemas.common import GridMindSchema, TimestampMixin, UUIDMixin
from gridmind.core.types import BatteryState


class BatteryAssetResponse(UUIDMixin, TimestampMixin):
    resource_id: UUID
    name_capacity_mwh: Decimal
    usable_capacity_mwh: Decimal
    max_charge_mw: Decimal
    max_discharge_mw: Decimal
    state_of_charge_pct: Decimal
    state: str
    cycle_count: int
    degradation_pct: Decimal
    round_trip_efficiency: Decimal


class ScheduleBatteryRequest(GridMindSchema):
    action: str
    power_mw: Decimal
    duration_minutes: int = Field(ge=1, le=1440)
    scheduled_at: datetime
    is_emergency: bool = False


class BatteryScheduleResponse(UUIDMixin, TimestampMixin):
    battery_id: UUID
    scheduled_at: datetime
    action: str
    target_power_mw: Decimal
    duration_minutes: int
    status: str
    is_emergency: bool


class TransitionBatteryStateRequest(GridMindSchema):
    target_state: BatteryState
    actor: str


class RecordCycleRequest(GridMindSchema):
    energy_charged_mwh: Decimal
    energy_discharged_mwh: Decimal


class BatteryCycleResponse(UUIDMixin, TimestampMixin):
    battery_id: UUID
    cycle_number: int
    energy_charged_mwh: Decimal
    energy_discharged_mwh: Decimal
    depth_of_discharge_pct: Decimal
    degradation_delta_pct: Decimal
