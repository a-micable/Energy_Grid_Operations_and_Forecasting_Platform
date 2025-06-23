from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from gridmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EventRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "event_records"

    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    aggregate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    routing_key: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class EventSubscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "event_subscriptions"

    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    handler_name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    filter_expression: Mapped[dict | None] = mapped_column(JSONB)
