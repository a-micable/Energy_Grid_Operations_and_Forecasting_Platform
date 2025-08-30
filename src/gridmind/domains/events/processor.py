from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from uuid import UUID

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from gridmind.core.events import DomainEvent, EventEnvelope
from gridmind.core.exceptions import EventOrderingError

logger = structlog.get_logger(__name__)

EventHandler = Callable[[DomainEvent], Coroutine[Any, Any, None]]


class EventProcessor:
    """Event routing, retry, and dead-letter handling."""

    def __init__(self, max_retries: int = 5) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._max_retries = max_retries
        self._sequence_trackers: dict[str, int] = defaultdict(int)
        self._processed: list[DomainEvent] = []
        self._dead_letters: list[EventEnvelope] = []

    def register(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def _aggregate_key(self, event: DomainEvent) -> str:
        return f"{event.aggregate_type}:{event.aggregate_id}"

    def validate_sequence(self, event: DomainEvent) -> None:
        if event.sequence_number is None:
            return
        key = self._aggregate_key(event)
        expected = self._sequence_trackers[key] + 1
        if event.sequence_number != expected:
            raise EventOrderingError(
                f"Expected sequence {expected} for {key}, got {event.sequence_number}",
                details={
                    "aggregate_type": event.aggregate_type,
                    "aggregate_id": str(event.aggregate_id),
                    "expected": expected,
                    "received": event.sequence_number,
                },
            )
        self._sequence_trackers[key] = event.sequence_number

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _execute_handler(self, handler: EventHandler, event: DomainEvent) -> None:
        await handler(event)

    async def process(self, envelope: EventEnvelope) -> bool:
        event = envelope.event
        try:
            self.validate_sequence(event)
        except EventOrderingError:
            logger.error("event_ordering_violation", event_id=str(event.event_id))
            self._dead_letters.append(envelope)
            return False

        handlers = self._handlers.get(event.event_type, [])
        handlers.extend(self._handlers.get("*", []))
        if not handlers:
            logger.warning("no_handler_for_event", event_type=event.event_type)
            return True

        for handler in handlers:
            try:
                await self._execute_handler(handler, event)
            except Exception as exc:
                envelope.retry_count += 1
                logger.error(
                    "event_handler_failed",
                    event_type=event.event_type,
                    retry=envelope.retry_count,
                    error=str(exc),
                )
                if envelope.is_expired:
                    self._dead_letters.append(envelope)
                    return False
                return False

        self._processed.append(event)
        return True

    async def reprocess_dead_letters(self) -> int:
        reprocessed = 0
        remaining: list[EventEnvelope] = []
        for envelope in self._dead_letters:
            envelope.retry_count = 0
            if await self.process(envelope):
                reprocessed += 1
            else:
                remaining.append(envelope)
        self._dead_letters = remaining
        return reprocessed

    @property
    def dead_letter_count(self) -> int:
        return len(self._dead_letters)
