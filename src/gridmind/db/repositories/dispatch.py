from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from gridmind.db.models.dispatch import DispatchInstruction, DispatchPlan, ResourceCapacity
from gridmind.db.repositories.base import BaseRepository


class DispatchPlanRepository(BaseRepository[DispatchPlan]):
    model = DispatchPlan

    async def get_with_instructions(self, plan_id: UUID) -> DispatchPlan | None:
        stmt = (
            select(DispatchPlan)
            .where(DispatchPlan.id == plan_id)
            .options(selectinload(DispatchPlan.instructions))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_active_for_zone(self, zone_id: UUID) -> list[DispatchPlan]:
        stmt = select(DispatchPlan).where(
            and_(
                DispatchPlan.zone_id == zone_id,
                DispatchPlan.status.in_(["scheduled", "active"]),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class DispatchInstructionRepository(BaseRepository[DispatchInstruction]):
    model = DispatchInstruction

    async def find_conflicts(
        self,
        resource_id: UUID,
        start: datetime,
        end: datetime,
        *,
        exclude_instruction_id: UUID | None = None,
    ) -> list[DispatchInstruction]:
        stmt = select(DispatchInstruction).where(
            and_(
                DispatchInstruction.resource_id == resource_id,
                DispatchInstruction.status.notin_(["cancelled", "completed"]),
                DispatchInstruction.scheduled_start < end,
                DispatchInstruction.scheduled_end > start,
            )
        )
        if exclude_instruction_id:
            stmt = stmt.where(DispatchInstruction.id != exclude_instruction_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ResourceCapacityRepository(BaseRepository[ResourceCapacity]):
    model = ResourceCapacity

    async def get_at_time(self, resource_id: UUID, at: datetime) -> ResourceCapacity | None:
        stmt = select(ResourceCapacity).where(
            and_(
                ResourceCapacity.resource_id == resource_id,
                ResourceCapacity.valid_from <= at,
                ResourceCapacity.valid_to >= at,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
