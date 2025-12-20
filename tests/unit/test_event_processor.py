from __future__ import annotations

from uuid import uuid4

import pytest

from gridmind.core.events import DomainEvent, EventEnvelope
from gridmind.core.exceptions import EventOrderingError
from gridmind.domains.events.processor import EventProcessor


class TestEventProcessor:
    @pytest.mark.asyncio
    async def test_process_event_with_handler(self) -> None:
        processor = EventProcessor()
        processed: list[str] = []

        async def handler(event: DomainEvent) -> None:
            processed.append(event.event_type)

        processor.register("test.event", handler)
        event = DomainEvent(
            event_type="test.event",
            aggregate_type="test",
            aggregate_id=uuid4(),
        )
        envelope = EventEnvelope(event=event, routing_key="test.event")
        result = await processor.process(envelope)
        assert result is True
        assert "test.event" in processed

    @pytest.mark.asyncio
    async def test_sequence_validation_detects_gaps(self) -> None:
        processor = EventProcessor()
        event = DomainEvent(
            event_type="test.event",
            aggregate_type="test",
            aggregate_id=uuid4(),
            sequence_number=2,
        )
        with pytest.raises(EventOrderingError):
            processor.validate_sequence(event)

    @pytest.mark.asyncio
    async def test_dead_letter_on_ordering_failure(self) -> None:
        processor = EventProcessor()
        event = DomainEvent(
            event_type="test.event",
            aggregate_type="test",
            aggregate_id=uuid4(),
            sequence_number=5,
        )
        envelope = EventEnvelope(event=event, routing_key="test.event")
        result = await processor.process(envelope)
        assert result is False
        assert processor.dead_letter_count == 1
