from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence
from uuid import UUID

import numpy as np
import structlog

from gridmind.core.exceptions import ForecastDriftError, ValidationError
from gridmind.core.types import ForecastHorizon, ForecastType

logger = structlog.get_logger(__name__)

DRIFT_THRESHOLD_PCT = Decimal("0.15")


@dataclass(frozen=True)
class ForecastPointData:
    timestamp: datetime
    value_mw: Decimal
    lower_bound_mw: Decimal | None = None
    upper_bound_mw: Decimal | None = None


@dataclass
class BacktestResult:
    mae: float
    rmse: float
    mape: float
    bias: float
    sample_count: int


class ForecastEngine:
    """Core forecasting engine with revision tracking and backtesting."""

    def __init__(self, drift_threshold_pct: Decimal = DRIFT_THRESHOLD_PCT) -> None:
        self._drift_threshold = drift_threshold_pct

    def generate_hourly_demand(
        self,
        base_load_mw: float,
        start: datetime,
        hours: int,
        *,
        noise_std: float = 0.05,
        seed: int | None = None,
    ) -> list[ForecastPointData]:
        rng = np.random.default_rng(seed)
        points: list[ForecastPointData] = []
        for h in range(hours):
            ts = start + timedelta(hours=h)
            hour_of_day = ts.hour
            daily_factor = 0.7 + 0.3 * np.sin((hour_of_day - 6) * np.pi / 12)
            seasonal = 1.0 + 0.1 * np.sin(ts.timetuple().tm_yday * 2 * np.pi / 365)
            noise = 1.0 + rng.normal(0, noise_std)
            value = base_load_mw * daily_factor * seasonal * noise
            ci = value * 0.08
            points.append(
                ForecastPointData(
                    timestamp=ts,
                    value_mw=Decimal(str(round(value, 4))),
                    lower_bound_mw=Decimal(str(round(value - ci, 4))),
                    upper_bound_mw=Decimal(str(round(value + ci, 4))),
                )
            )
        return points

    def generate_renewable_output(
        self,
        capacity_mw: float,
        forecast_type: ForecastType,
        start: datetime,
        hours: int,
        *,
        seed: int | None = None,
    ) -> list[ForecastPointData]:
        rng = np.random.default_rng(seed)
        points: list[ForecastPointData] = []
        for h in range(hours):
            ts = start + timedelta(hours=h)
            hour = ts.hour
            if forecast_type == ForecastType.SOLAR:
                if 6 <= hour <= 20:
                    factor = np.sin((hour - 6) * np.pi / 14)
                else:
                    factor = 0.0
            elif forecast_type == ForecastType.WIND:
                factor = 0.3 + 0.5 * abs(np.sin(hour * np.pi / 12 + rng.normal(0, 0.3)))
            else:
                factor = 0.5 + 0.3 * rng.random()
            value = capacity_mw * factor
            uncertainty = value * (0.15 if forecast_type == ForecastType.WIND else 0.08)
            points.append(
                ForecastPointData(
                    timestamp=ts,
                    value_mw=Decimal(str(round(value, 4))),
                    lower_bound_mw=Decimal(str(round(max(0, value - uncertainty), 4))),
                    upper_bound_mw=Decimal(str(round(value + uncertainty, 4))),
                )
            )
        return points

    def compute_revision_delta(
        self,
        previous: Sequence[ForecastPointData],
        revised: Sequence[ForecastPointData],
    ) -> Decimal:
        if len(previous) != len(revised):
            raise ValidationError("Revision point count mismatch")
        if not previous:
            return Decimal("0")
        deltas: list[float] = []
        for p, r in zip(previous, revised):
            if float(p.value_mw) == 0:
                continue
            delta = abs(float(r.value_mw) - float(p.value_mw)) / float(p.value_mw)
            deltas.append(delta)
        if not deltas:
            return Decimal("0")
        return Decimal(str(round(sum(deltas) / len(deltas), 6)))

    def validate_revision(
        self,
        forecast_id: UUID,
        previous: Sequence[ForecastPointData],
        revised: Sequence[ForecastPointData],
    ) -> Decimal:
        delta = self.compute_revision_delta(previous, revised)
        if delta > self._drift_threshold:
            logger.warning(
                "forecast_drift_detected",
                forecast_id=str(forecast_id),
                delta_pct=float(delta),
            )
            raise ForecastDriftError(forecast_id, float(delta))
        return delta

    def backtest(
        self,
        forecast_points: Sequence[ForecastPointData],
        actuals: dict[datetime, Decimal],
    ) -> BacktestResult:
        errors: list[float] = []
        pct_errors: list[float] = []
        for point in forecast_points:
            actual = actuals.get(point.timestamp)
            if actual is None:
                continue
            forecast_val = float(point.value_mw)
            actual_val = float(actual)
            error = actual_val - forecast_val
            errors.append(error)
            if actual_val != 0:
                pct_errors.append(abs(error) / actual_val)
        if not errors:
            return BacktestResult(0.0, 0.0, 0.0, 0.0, 0)
        arr = np.array(errors)
        mae = float(np.mean(np.abs(arr)))
        rmse = float(np.sqrt(np.mean(arr**2)))
        mape = float(np.mean(pct_errors)) if pct_errors else 0.0
        bias = float(np.mean(arr))
        return BacktestResult(mae, rmse, mape, bias, len(errors))

    def apply_confidence_intervals(
        self,
        points: list[ForecastPointData],
        confidence_level: Decimal,
    ) -> list[ForecastPointData]:
        z_scores = {Decimal("0.90"): 1.645, Decimal("0.95"): 1.96, Decimal("0.99"): 2.576}
        z = z_scores.get(confidence_level, 1.96)
        result: list[ForecastPointData] = []
        for p in points:
            spread = float(p.value_mw) * 0.05 * z
            result.append(
                ForecastPointData(
                    timestamp=p.timestamp,
                    value_mw=p.value_mw,
                    lower_bound_mw=Decimal(str(round(max(0, float(p.value_mw) - spread), 4))),
                    upper_bound_mw=Decimal(str(round(float(p.value_mw) + spread, 4))),
                )
            )
        return result
