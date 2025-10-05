from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from gridmind.api.schemas.common import GridMindSchema, TimestampMixin, UUIDMixin


class OptimizationRunRequest(GridMindSchema):
    zone_id: UUID
    run_type: str
    demand_mw: float
    available_reserve_mw: float = 300.0
    reserve_margin_pct: float = 0.15
    resources: list[dict]
    timeout_seconds: int = 120


class OptimizationRunResponse(UUIDMixin, TimestampMixin):
    zone_id: UUID
    run_type: str
    status: str
    objective_value: Decimal | None = None
    solver_status: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ScenarioRequest(GridMindSchema):
    scenario_name: str
    parameters: dict


class ScenarioResponse(UUIDMixin):
    scenario_name: str
    objective_value: Decimal | None = None
    rank: int | None = None
    is_selected: bool = False
