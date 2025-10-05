from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from gridmind.api.schemas.common import GridMindSchema, TimestampMixin, UUIDMixin
from gridmind.core.types import ForecastHorizon, ForecastType


class CreateForecastRequest(GridMindSchema):
    zone_id: UUID
    forecast_type: ForecastType
    horizon: ForecastHorizon
    base_load_mw: float = 1500.0
    hours: int = Field(default=48, ge=1, le=168)
    model_name: str = "gridmind-ensemble-v3"


class ForecastPointResponse(GridMindSchema):
    timestamp: datetime
    value_mw: Decimal
    lower_bound_mw: Decimal | None = None
    upper_bound_mw: Decimal | None = None


class ForecastRunResponse(UUIDMixin, TimestampMixin):
    zone_id: UUID
    forecast_type: str
    horizon: str
    model_name: str
    model_version: str
    status: str
    metrics: dict = Field(default_factory=dict)


class ReviseForecastRequest(GridMindSchema):
    reason: str
    revised_by: str
    force: bool = False
    points: list[ForecastPointResponse]


class BacktestRequest(GridMindSchema):
    version_id: UUID
    actuals: dict[str, Decimal]
