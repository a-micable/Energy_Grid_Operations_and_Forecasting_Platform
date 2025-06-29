from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from gridmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OutagePlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "outage_plans"

    zone_id: Mapped[UUID] = mapped_column(ForeignKey("grid_zones.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    outage_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    impact_mw: Mapped[float] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(256), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(256))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class OutageResource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "outage_resources"
    __table_args__ = (
        UniqueConstraint("outage_id", "resource_id", name="uq_outage_resource"),
    )

    outage_id: Mapped[UUID] = mapped_column(ForeignKey("outage_plans.id"), nullable=False, index=True)
    resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("generation_resources.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), default="affected")


class OutageDependency(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "outage_dependencies"
    __table_args__ = (
        UniqueConstraint("outage_id", "depends_on_outage_id", name="uq_outage_dependency"),
    )

    outage_id: Mapped[UUID] = mapped_column(ForeignKey("outage_plans.id"), nullable=False, index=True)
    depends_on_outage_id: Mapped[UUID] = mapped_column(
        ForeignKey("outage_plans.id"), nullable=False, index=True
    )
    dependency_type: Mapped[str] = mapped_column(String(64), nullable=False)
    is_hard: Mapped[bool] = mapped_column(default=True)
