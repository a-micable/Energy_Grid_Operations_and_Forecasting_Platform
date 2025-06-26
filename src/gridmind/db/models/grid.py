from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gridmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GridZone(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "grid_zones"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    peak_demand_mw: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    resources: Mapped[list["GenerationResource"]] = relationship(back_populates="zone")


class GenerationResource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "generation_resources"

    zone_id: Mapped[UUID] = mapped_column(ForeignKey("grid_zones.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    capacity_mw: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    min_output_mw: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"))
    ramp_rate_mw_per_min: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("1"))
    marginal_cost_per_mwh: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    emission_rate_kg_co2_per_mwh: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    dispatch_priority: Mapped[int] = mapped_column(default=100)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_renewable: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    zone: Mapped[GridZone] = relationship(back_populates="resources")
