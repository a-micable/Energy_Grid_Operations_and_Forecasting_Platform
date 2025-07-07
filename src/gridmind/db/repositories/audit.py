from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, desc, select

from gridmind.db.models.audit import AuditEntry, ComplianceReport
from gridmind.db.repositories.base import BaseRepository


class AuditEntryRepository(BaseRepository[AuditEntry]):
    model = AuditEntry

    async def get_entity_history(
        self, entity_type: str, entity_id: UUID, *, limit: int = 100
    ) -> list[AuditEntry]:
        stmt = (
            select(AuditEntry)
            .where(
                and_(
                    AuditEntry.entity_type == entity_type,
                    AuditEntry.entity_id == entity_id,
                )
            )
            .order_by(desc(AuditEntry.occurred_at))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_timeline(
        self, start: datetime, end: datetime, *, entity_type: str | None = None
    ) -> list[AuditEntry]:
        stmt = select(AuditEntry).where(
            and_(AuditEntry.occurred_at >= start, AuditEntry.occurred_at <= end)
        )
        if entity_type:
            stmt = stmt.where(AuditEntry.entity_type == entity_type)
        stmt = stmt.order_by(AuditEntry.occurred_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def reconstruct_state(
        self, entity_type: str, entity_id: UUID, at: datetime
    ) -> dict | None:
        stmt = (
            select(AuditEntry)
            .where(
                and_(
                    AuditEntry.entity_type == entity_type,
                    AuditEntry.entity_id == entity_id,
                    AuditEntry.occurred_at <= at,
                )
            )
            .order_by(desc(AuditEntry.occurred_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        entry = result.scalar_one_or_none()
        return entry.after_state if entry else None


class ComplianceReportRepository(BaseRepository[ComplianceReport]):
    model = ComplianceReport
