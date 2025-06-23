from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gridmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DispatchPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dispatch_plans"

    zone_id: Mapped[UUID] = mapped_column(ForeignKey("grid_zones.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    horizon_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    total_emissions_kg: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    optimization_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("optimization_runs.id"))
    created_by: Mapped[str] = mapped_column(String(256), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    instructions: Mapped[list["DispatchInstruction"]] = relationship(back_populates="plan")


class DispatchInstruction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dispatch_instructions"

    plan_id: Mapped[UUID] = mapped_column(ForeignKey("dispatch_plans.id"), nullable=False, index=True)
    resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("generation_resources.id"), nullable=False, index=True
    )
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_output_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    actual_output_mw: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    marginal_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    plan: Mapped[DispatchPlan] = relationship(back_populates="instructions")


class ResourceCapacity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resource_capacity"

    resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("generation_resources.id"), nullable=False, index=True
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    derated_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
