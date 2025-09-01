from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.core.events import DomainEvent
from gridmind.core.types import EventStatus
from gridmind.db.models.events import EventRecord
from gridmind.db.repositories.events import EventRecordRepository
from gridmind.domains.events.processor import EventProcessor


class EventService:
    def __init__(
        self,
        session: AsyncSession,
        processor: EventProcessor | None = None,
    ) -> None:
        self._session = session
        self._repo = EventRecordRepository(session)
        self._processor = processor or EventProcessor()

    async def ingest_event(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict,
        *,
        correlation_id: UUID | None = None,
        sequence_number: int | None = None,
        routing_key: str | None = None,
    ) -> EventRecord:
        record = EventRecord(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            status=EventStatus.PENDING.value,
            routing_key=routing_key or event_type,
            correlation_id=correlation_id,
            sequence_number=sequence_number,
            occurred_at=datetime.now(timezone.utc),
        )
        await self._repo.add(record)
        return record

    async def process_pending(self, limit: int = 100) -> int:
        pending = await self._repo.get_pending(limit=limit)
        processed = 0
        for record in pending:
            event = DomainEvent(
                event_type=record.event_type,
                aggregate_type=record.aggregate_type,
                aggregate_id=record.aggregate_id,
                payload=record.payload,
                correlation_id=record.correlation_id,
                sequence_number=record.sequence_number,
            )
            from gridmind.core.events import EventEnvelope
            envelope = EventEnvelope(event=event, routing_key=record.routing_key)
            if await self._processor.process(envelope):
                record.status = EventStatus.COMPLETED.value
                record.processed_at = datetime.now(timezone.utc)
                processed += 1
            else:
                record.retry_count += 1
                if record.retry_count >= 5:
                    record.status = EventStatus.DEAD_LETTER.value
        await self._session.flush()
        return processed
