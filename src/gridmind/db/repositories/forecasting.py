from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gridmind.db.models.forecasting import ForecastPoint, ForecastRevision, ForecastRun, ForecastVersion
from gridmind.db.repositories.base import BaseRepository


class ForecastRunRepository(BaseRepository[ForecastRun]):
    model = ForecastRun

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_with_versions(self, run_id: UUID) -> ForecastRun | None:
        stmt = (
            select(ForecastRun)
            .where(ForecastRun.id == run_id)
            .options(selectinload(ForecastRun.versions))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_zone(
        self, zone_id: UUID, *, forecast_type: str | None = None, limit: int = 50
    ) -> list[ForecastRun]:
        stmt = select(ForecastRun).where(ForecastRun.zone_id == zone_id)
        if forecast_type:
            stmt = stmt.where(ForecastRun.forecast_type == forecast_type)
        stmt = stmt.order_by(desc(ForecastRun.created_at)).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ForecastVersionRepository(BaseRepository[ForecastVersion]):
    model = ForecastVersion

    async def get_current_for_run(self, run_id: UUID) -> ForecastVersion | None:
        stmt = select(ForecastVersion).where(
            and_(ForecastVersion.run_id == run_id, ForecastVersion.is_current.is_(True))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_points(self, version_id: UUID) -> ForecastVersion | None:
        stmt = (
            select(ForecastVersion)
            .where(ForecastVersion.id == version_id)
            .options(selectinload(ForecastVersion.points))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def supersede_current(self, run_id: UUID, new_version: ForecastVersion) -> None:
        current = await self.get_current_for_run(run_id)
        if current:
            current.is_current = False
            current.superseded_by_id = new_version.id
        new_version.is_current = True
        await self._session.flush()


class ForecastPointRepository(BaseRepository[ForecastPoint]):
    model = ForecastPoint

    async def get_range(
        self, version_id: UUID, start: datetime, end: datetime
    ) -> list[ForecastPoint]:
        stmt = (
            select(ForecastPoint)
            .where(
                and_(
                    ForecastPoint.version_id == version_id,
                    ForecastPoint.timestamp >= start,
                    ForecastPoint.timestamp <= end,
                )
            )
            .order_by(ForecastPoint.timestamp)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_insert(self, points: list[ForecastPoint]) -> None:
        self._session.add_all(points)
        await self._session.flush()


class ForecastRevisionRepository(BaseRepository[ForecastRevision]):
    model = ForecastRevision

    async def list_for_version(self, version_id: UUID) -> list[ForecastRevision]:
        stmt = (
            select(ForecastRevision)
            .where(ForecastRevision.version_id == version_id)
            .order_by(ForecastRevision.revision_number)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
