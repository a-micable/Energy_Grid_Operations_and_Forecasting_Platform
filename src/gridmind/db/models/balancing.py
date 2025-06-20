from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from gridmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BalancingSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "balancing_snapshots"

    zone_id: Mapped[UUID] = mapped_column(ForeignKey("grid_zones.id"), nullable=False, index=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    supply_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    demand_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    net_imbalance_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    frequency_hz: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    reserve_available_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class ReserveCapacity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reserve_capacity"

    zone_id: Mapped[UUID] = mapped_column(ForeignKey("grid_zones.id"), nullable=False, index=True)
    reserve_type: Mapped[str] = mapped_column(String(32), nullable=False)
    capacity_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    committed_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0"))
    available_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BalancingAction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "balancing_actions"

    zone_id: Mapped[UUID] = mapped_column(ForeignKey("grid_zones.id"), nullable=False, index=True)
    snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("balancing_snapshots.id"))
    resource_id: Mapped[UUID | None] = mapped_column(ForeignKey("generation_resources.id"))
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    target_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    actual_mw: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    priority: Mapped[int] = mapped_column(default=50)
    initiated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    initiated_by: Mapped[str] = mapped_column(String(256), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
