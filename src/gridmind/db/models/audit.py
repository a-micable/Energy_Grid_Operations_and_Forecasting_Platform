from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from gridmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_entries"

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(256), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    before_state: Mapped[dict | None] = mapped_column(JSONB)
    after_state: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class ComplianceReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "compliance_reports"

    report_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    generated_by: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    findings: Mapped[list] = mapped_column(JSONB, default=list)
