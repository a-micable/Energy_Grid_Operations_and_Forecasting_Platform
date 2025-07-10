from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.db.models.balancing import BalancingAction, BalancingSnapshot, ReserveCapacity
from gridmind.db.repositories.base import BaseRepository


class BalancingSnapshotRepository(BaseRepository[BalancingSnapshot]):
    model = BalancingSnapshot

    async def get_latest(self, zone_id: UUID) -> BalancingSnapshot | None:
        stmt = (
            select(BalancingSnapshot)
            .where(BalancingSnapshot.zone_id == zone_id)
            .order_by(desc(BalancingSnapshot.snapshot_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_history(
        self, zone_id: UUID, start: datetime, end: datetime
    ) -> list[BalancingSnapshot]:
        stmt = (
            select(BalancingSnapshot)
            .where(
                and_(
                    BalancingSnapshot.zone_id == zone_id,
                    BalancingSnapshot.snapshot_at >= start,
                    BalancingSnapshot.snapshot_at <= end,
                )
            )
            .order_by(BalancingSnapshot.snapshot_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ReserveCapacityRepository(BaseRepository[ReserveCapacity]):
    model = ReserveCapacity

    async def get_active(self, zone_id: UUID, at: datetime) -> list[ReserveCapacity]:
        stmt = select(ReserveCapacity).where(
            and_(
                ReserveCapacity.zone_id == zone_id,
                ReserveCapacity.valid_from <= at,
                ReserveCapacity.valid_to >= at,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class BalancingActionRepository(BaseRepository[BalancingAction]):
    model = BalancingAction

    async def list_pending(self, zone_id: UUID) -> list[BalancingAction]:
        stmt = (
            select(BalancingAction)
            .where(
                and_(
                    BalancingAction.zone_id == zone_id,
                    BalancingAction.status == "pending",
                )
            )
            .order_by(BalancingAction.priority)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
