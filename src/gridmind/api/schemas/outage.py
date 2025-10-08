from __future__ import annotations

from datetime import datetime
from uuid import UUID

from gridmind.api.schemas.common import GridMindSchema, TimestampMixin, UUIDMixin
from gridmind.core.types import OutageStatus, OutageType


class CreateOutageRequest(GridMindSchema):
    zone_id: UUID
    title: str
    outage_type: OutageType
    planned_start: datetime
    planned_end: datetime
    impact_mw: float
    resource_ids: list[UUID]
    created_by: str
    description: str | None = None


class OutageResponse(UUIDMixin, TimestampMixin):
    zone_id: UUID
    title: str
    outage_type: str
    status: str
    planned_start: datetime
    planned_end: datetime
    impact_mw: float


class TransitionOutageRequest(GridMindSchema):
    target_status: OutageStatus
    actor: str


class AddDependencyRequest(GridMindSchema):
    depends_on_outage_id: UUID
    dependency_type: str = "sequential"
    is_hard: bool = True
