from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gridmind.db.models.outage import OutageDependency, OutagePlan, OutageResource
from gridmind.db.repositories.base import BaseRepository


class OutagePlanRepository(BaseRepository[OutagePlan]):
    model = OutagePlan

    async def get_with_resources(self, outage_id: UUID) -> OutagePlan | None:
        stmt = select(OutagePlan).where(OutagePlan.id == outage_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_overlapping(
        self,
        zone_id: UUID,
        start: datetime,
        end: datetime,
        *,
        exclude_id: UUID | None = None,
    ) -> list[OutagePlan]:
        stmt = select(OutagePlan).where(
            and_(
                OutagePlan.zone_id == zone_id,
                OutagePlan.status.notin_(["cancelled", "completed"]),
                OutagePlan.planned_start < end,
                OutagePlan.planned_end > start,
            )
        )
        if exclude_id:
            stmt = stmt.where(OutagePlan.id != exclude_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_status(self, status: str, limit: int = 100) -> list[OutagePlan]:
        stmt = (
            select(OutagePlan)
            .where(OutagePlan.status == status)
            .order_by(OutagePlan.planned_start)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class OutageDependencyRepository(BaseRepository[OutageDependency]):
    model = OutageDependency

    async def get_dependencies(self, outage_id: UUID) -> list[OutageDependency]:
        stmt = select(OutageDependency).where(OutageDependency.outage_id == outage_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_dependents(self, outage_id: UUID) -> list[OutageDependency]:
        stmt = select(OutageDependency).where(
            OutageDependency.depends_on_outage_id == outage_id
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def has_cycle(self, outage_id: UUID, depends_on_id: UUID) -> bool:
        """Detect if adding dependency would create a cycle."""
        visited: set[UUID] = set()
        queue = [depends_on_id]
        while queue:
            current = queue.pop(0)
            if current == outage_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            deps = await self.get_dependencies(current)
            queue.extend(d.depends_on_outage_id for d in deps)
        return False


class OutageResourceRepository(BaseRepository[OutageResource]):
    model = OutageResource

    async def list_for_outage(self, outage_id: UUID) -> list[OutageResource]:
        stmt = select(OutageResource).where(OutageResource.outage_id == outage_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_conflicts(
        self, resource_id: UUID, start: datetime, end: datetime
    ) -> list[OutageResource]:
        stmt = (
            select(OutageResource)
            .join(OutagePlan)
            .where(
                and_(
                    OutageResource.resource_id == resource_id,
                    OutagePlan.status.notin_(["cancelled", "completed"]),
                    OutagePlan.planned_start < end,
                    OutagePlan.planned_end > start,
                )
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
