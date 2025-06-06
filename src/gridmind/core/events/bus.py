from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import structlog

from gridmind.core.events.base import DomainEvent, EventEnvelope

logger = structlog.get_logger(__name__)

EventHandler = Callable[[DomainEvent], Awaitable[None]]


class InMemoryEventBus:
    """In-process event bus for testing and local development."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._published: list[DomainEvent] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        self._published.append(event)
        handlers = self._handlers.get(event.event_type, [])
        handlers.extend(self._handlers.get("*", []))
        for handler in handlers:
            await handler(event)

    @property
    def published_events(self) -> list[DomainEvent]:
        return list(self._published)


class RedisEventBus:
    """Redis-backed event bus with pub/sub and persistence."""

    STREAM_KEY = "gridmind:events:stream"
    DLQ_KEY = "gridmind:events:dlq"

    def __init__(self, redis_client: Any, max_retries: int = 5) -> None:
        self._redis = redis_client
        self._max_retries = max_retries
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent, *, routing_key: str | None = None) -> UUID:
        envelope = EventEnvelope(
            event=event,
            routing_key=routing_key or event.event_type,
            max_retries=self._max_retries,
        )
        data = envelope.model_dump_json()
        await self._redis.xadd(self.STREAM_KEY, {"data": data})
        await self._redis.publish(envelope.routing_key, data)
        logger.info("event_published", event_type=event.event_type, event_id=str(event.event_id))
        return envelope.envelope_id

    async def publish_to_dlq(self, envelope: EventEnvelope, error: str) -> None:
        payload = json.loads(envelope.model_dump_json())
        payload["error"] = error
        payload["failed_at"] = envelope.event.occurred_at.isoformat()
        await self._redis.lpush(self.DLQ_KEY, json.dumps(payload))
        logger.error(
            "event_dead_lettered",
            event_type=envelope.event.event_type,
            retry_count=envelope.retry_count,
            error=error,
        )

    async def dispatch(self, envelope: EventEnvelope) -> bool:
        handlers = self._handlers.get(envelope.event.event_type, [])
        handlers.extend(self._handlers.get("*", []))
        if not handlers:
            return True
        try:
            for handler in handlers:
                await handler(envelope.event)
            return True
        except Exception as exc:
            envelope.retry_count += 1
            if envelope.is_expired:
                await self.publish_to_dlq(envelope, str(exc))
            else:
                await self._redis.xadd(
                    self.STREAM_KEY,
                    {"data": envelope.model_dump_json(), "retry": str(envelope.retry_count)},
                )
            return False
