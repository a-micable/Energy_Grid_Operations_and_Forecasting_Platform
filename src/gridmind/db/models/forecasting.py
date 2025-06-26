from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gridmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ForecastRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "forecast_runs"

    zone_id: Mapped[UUID] = mapped_column(ForeignKey("grid_zones.id"), nullable=False, index=True)
    forecast_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    horizon: Mapped[str] = mapped_column(String(16), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)

    versions: Mapped[list["ForecastVersion"]] = relationship(back_populates="run")


class ForecastVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "forecast_versions"
    __table_args__ = (UniqueConstraint("run_id", "version_number", name="uq_forecast_version"),)

    run_id: Mapped[UUID] = mapped_column(ForeignKey("forecast_runs.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.95"))
    revision_reason: Mapped[str | None] = mapped_column(Text)
    superseded_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("forecast_versions.id"))

    run: Mapped[ForecastRun] = relationship(back_populates="versions")
    points: Mapped[list["ForecastPoint"]] = relationship(back_populates="version")
    revisions: Mapped[list["ForecastRevision"]] = relationship(back_populates="version")


class ForecastPoint(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "forecast_points"
    __table_args__ = (
        UniqueConstraint("version_id", "timestamp", name="uq_forecast_point_timestamp"),
    )

    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("forecast_versions.id"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    value_mw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    lower_bound_mw: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    upper_bound_mw: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    actual_mw: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))

    version: Mapped[ForecastVersion] = relationship(back_populates="points")


class ForecastRevision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "forecast_revisions"

    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("forecast_versions.id"), nullable=False, index=True
    )
    previous_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("forecast_versions.id"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    delta_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    revised_by: Mapped[str] = mapped_column(String(256), nullable=False)
    drift_flagged: Mapped[bool] = mapped_column(default=False)

    version: Mapped[ForecastVersion] = relationship(
        back_populates="revisions", foreign_keys=[version_id]
    )
