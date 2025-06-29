from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gridmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OptimizationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "optimization_runs"

    zone_id: Mapped[UUID] = mapped_column(ForeignKey("grid_zones.id"), nullable=False, index=True)
    run_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    objective_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    constraints: Mapped[dict] = mapped_column(JSONB, default=dict)
    solution: Mapped[dict] = mapped_column(JSONB, default=dict)
    solver_name: Mapped[str] = mapped_column(String(64), default="scipy_milp")
    solver_status: Mapped[str | None] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(Text)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)

    scenarios: Mapped[list["OptimizationScenario"]] = relationship(back_populates="run")


class OptimizationScenario(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "optimization_scenarios"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("optimization_runs.id"), nullable=False, index=True)
    scenario_name: Mapped[str] = mapped_column(String(256), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    objective_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    solution: Mapped[dict] = mapped_column(JSONB, default=dict)
    rank: Mapped[int | None] = mapped_column(Integer)
    is_selected: Mapped[bool] = mapped_column(default=False)

    run: Mapped[OptimizationRun] = relationship(back_populates="scenarios")
