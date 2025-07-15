from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select

from gridmind.db.models.events import EventRecord, EventSubscription
from gridmind.db.repositories.base import BaseRepository


class EventRecordRepository(BaseRepository[EventRecord]):
    model = EventRecord

    async def get_pending(self, limit: int = 100) -> list[EventRecord]:
        stmt = (
            select(EventRecord)
            .where(EventRecord.status == "pending")
            .order_by(EventRecord.occurred_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_correlation(self, correlation_id: UUID) -> list[EventRecord]:
        stmt = (
            select(EventRecord)
            .where(EventRecord.correlation_id == correlation_id)
            .order_by(EventRecord.sequence_number)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def check_sequence_gap(
        self, aggregate_type: str, aggregate_id: UUID, expected_seq: int
    ) -> bool:
        stmt = select(EventRecord).where(
            and_(
                EventRecord.aggregate_type == aggregate_type,
                EventRecord.aggregate_id == aggregate_id,
                EventRecord.sequence_number == expected_seq,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None


class EventSubscriptionRepository(BaseRepository[EventSubscription]):
    model = EventSubscription

    async def get_active_handlers(self, event_type: str) -> list[EventSubscription]:
        stmt = select(EventSubscription).where(
            and_(
                EventSubscription.event_type == event_type,
                EventSubscription.is_active.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
