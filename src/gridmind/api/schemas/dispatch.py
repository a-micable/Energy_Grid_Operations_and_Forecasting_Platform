from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from gridmind.api.schemas.common import GridMindSchema, TimestampMixin, UUIDMixin


class ResourceOfferRequest(GridMindSchema):
    resource_id: UUID
    resource_type: str
    min_output_mw: Decimal
    max_output_mw: Decimal
    marginal_cost: Decimal
    emission_rate: Decimal = Decimal("0")
    dispatch_priority: int = 100


class CreateDispatchPlanRequest(GridMindSchema):
    zone_id: UUID
    demand_mw: Decimal
    resources: list[ResourceOfferRequest]
    horizon_start: datetime
    horizon_end: datetime
    created_by: str


class DispatchPlanResponse(UUIDMixin, TimestampMixin):
    zone_id: UUID
    status: str
    horizon_start: datetime
    horizon_end: datetime
    total_cost: Decimal | None = None
    total_emissions_kg: Decimal | None = None
