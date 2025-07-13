from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select

from gridmind.db.models.battery import BatteryAsset, BatteryCycle, BatterySchedule
from gridmind.db.repositories.base import BaseRepository


class BatteryAssetRepository(BaseRepository[BatteryAsset]):
    model = BatteryAsset

    async def get_by_resource(self, resource_id: UUID) -> BatteryAsset | None:
        stmt = select(BatteryAsset).where(BatteryAsset.resource_id == resource_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_available_for_dispatch(self) -> list[BatteryAsset]:
        stmt = select(BatteryAsset).where(BatteryAsset.state != "maintenance")
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class BatteryScheduleRepository(BaseRepository[BatterySchedule]):
    model = BatterySchedule

    async def find_overlapping(
        self, battery_id: UUID, start: datetime, end: datetime
    ) -> list[BatterySchedule]:
        stmt = select(BatterySchedule).where(
            and_(
                BatterySchedule.battery_id == battery_id,
                BatterySchedule.status.in_(["scheduled", "active"]),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class BatteryCycleRepository(BaseRepository[BatteryCycle]):
    model = BatteryCycle

    async def get_latest_cycle(self, battery_id: UUID) -> BatteryCycle | None:
        stmt = (
            select(BatteryCycle)
            .where(BatteryCycle.battery_id == battery_id)
            .order_by(BatteryCycle.cycle_number.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
