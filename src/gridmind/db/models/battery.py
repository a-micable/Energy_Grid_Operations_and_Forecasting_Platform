from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from gridmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BatteryAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "battery_assets"

    resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("generation_resources.id"), unique=True, nullable=False
    )
    name_capacity_mwh: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    usable_capacity_mwh: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    max_charge_mw: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    max_discharge_mw: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    state_of_charge_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="idle")
    cycle_count: Mapped[int] = mapped_column(Integer, default=0)
    degradation_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    round_trip_efficiency: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.90"))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class BatteryCycle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "battery_cycles"

    battery_id: Mapped[UUID] = mapped_column(ForeignKey("battery_assets.id"), nullable=False, index=True)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    energy_charged_mwh: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))
    energy_discharged_mwh: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))
    depth_of_discharge_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    degradation_delta_pct: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=Decimal("0"))


class BatterySchedule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "battery_schedules"

    battery_id: Mapped[UUID] = mapped_column(ForeignKey("battery_assets.id"), nullable=False, index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    target_power_mw: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    target_soc_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    optimization_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("optimization_runs.id"))
    is_emergency: Mapped[bool] = mapped_column(default=False)
