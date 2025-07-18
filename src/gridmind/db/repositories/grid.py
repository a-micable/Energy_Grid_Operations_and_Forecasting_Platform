from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from gridmind.db.models.grid import GenerationResource, GridZone
from gridmind.db.repositories.base import BaseRepository


class GridZoneRepository(BaseRepository[GridZone]):
    model = GridZone

    async def get_by_code(self, code: str) -> GridZone | None:
        stmt = select(GridZone).where(GridZone.code == code)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> list[GridZone]:
        stmt = select(GridZone).where(GridZone.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class GenerationResourceRepository(BaseRepository[GenerationResource]):
    model = GenerationResource

    async def get_by_code(self, code: str) -> GenerationResource | None:
        stmt = select(GenerationResource).where(GenerationResource.code == code)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_zone(self, zone_id: UUID) -> list[GenerationResource]:
        stmt = select(GenerationResource).where(GenerationResource.zone_id == zone_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_available_by_zone(self, zone_id: UUID) -> list[GenerationResource]:
        stmt = select(GenerationResource).where(
            GenerationResource.zone_id == zone_id,
            GenerationResource.is_available.is_(True),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_type(self, resource_type: str) -> list[GenerationResource]:
        stmt = select(GenerationResource).where(GenerationResource.resource_type == resource_type)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
