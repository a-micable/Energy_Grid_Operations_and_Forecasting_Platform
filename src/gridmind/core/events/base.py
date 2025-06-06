from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    sequence_number: int | None = None
    version: int = 1

    model_config = {"frozen": True}


class EventEnvelope(BaseModel):
    """Wrapper for events in the message queue."""

    envelope_id: UUID = Field(default_factory=uuid4)
    event: DomainEvent
    retry_count: int = 0
    max_retries: int = 5
    routing_key: str
    priority: int = 0
    scheduled_at: datetime | None = None

    @property
    def is_expired(self) -> bool:
        return self.retry_count >= self.max_retries
