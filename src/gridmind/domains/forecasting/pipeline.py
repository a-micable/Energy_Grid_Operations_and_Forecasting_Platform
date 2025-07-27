from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog

from gridmind.core.types import ForecastHorizon, ForecastType
from gridmind.domains.forecasting.engine import BacktestResult, ForecastEngine, ForecastPointData

logger = structlog.get_logger(__name__)


@dataclass
class PipelineStage:
    name: str
    status: str = "pending"
    output: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class PipelineResult:
    run_id: UUID | None
    stages: list[PipelineStage]
    points: list[ForecastPointData]
    backtest: BacktestResult | None = None
    status: str = "pending"


class ForecastPipeline:
    """Multi-stage forecast generation pipeline with validation and backtesting."""

    def __init__(self, engine: ForecastEngine | None = None) -> None:
        self._engine = engine or ForecastEngine()

    async def run(
        self,
        zone_id: UUID,
        forecast_type: ForecastType,
        horizon: ForecastHorizon,
        *,
        base_load_mw: float = 1500.0,
        hours: int = 48,
        historical_actuals: dict[datetime, Decimal] | None = None,
        seed: int | None = None,
    ) -> PipelineResult:
        stages: list[PipelineStage] = []
        start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        # Stage 1: Data preparation
        prep = PipelineStage(name="data_preparation")
        prep.status = "running"
        prep.output = {
            "zone_id": str(zone_id),
            "forecast_type": forecast_type.value,
            "horizon": horizon.value,
            "base_load_mw": base_load_mw,
            "hours": hours,
        }
        prep.status = "completed"
        stages.append(prep)

        # Stage 2: Model execution
        model = PipelineStage(name="model_execution")
        model.status = "running"
        if forecast_type == ForecastType.DEMAND:
            points = self._engine.generate_hourly_demand(base_load_mw, start, hours, seed=seed)
        elif forecast_type in (ForecastType.SOLAR, ForecastType.WIND, ForecastType.RENEWABLE):
            points = self._engine.generate_renewable_output(
                base_load_mw, forecast_type, start, hours, seed=seed
            )
        else:
            points = self._engine.generate_hourly_demand(base_load_mw, start, hours, seed=seed)
        model.output = {"point_count": len(points)}
        model.status = "completed"
        stages.append(model)

        # Stage 3: Confidence intervals
        ci = PipelineStage(name="confidence_intervals")
        ci.status = "running"
        points = self._engine.apply_confidence_intervals(points, Decimal("0.95"))
        ci.output = {"confidence_level": "0.95"}
        ci.status = "completed"
        stages.append(ci)

        # Stage 4: Validation
        validation = PipelineStage(name="validation")
        validation.status = "running"
        null_points = [p for p in points if p.value_mw <= 0 and forecast_type == ForecastType.DEMAND]
        validation.output = {
            "valid": len(null_points) == 0,
            "null_points": len(null_points),
            "min_value": str(min(p.value_mw for p in points)),
            "max_value": str(max(p.value_mw for p in points)),
        }
        validation.status = "completed" if validation.output["valid"] else "failed"
        stages.append(validation)

        # Stage 5: Backtesting (optional)
        backtest_result = None
        if historical_actuals:
            bt = PipelineStage(name="backtesting")
            bt.status = "running"
            backtest_result = self._engine.backtest(points[: min(len(points), len(historical_actuals))], historical_actuals)
            bt.output = {
                "mae": backtest_result.mae,
                "rmse": backtest_result.rmse,
                "mape": backtest_result.mape,
                "sample_count": backtest_result.sample_count,
            }
            bt.status = "completed"
            stages.append(bt)

        status = "completed" if all(s.status == "completed" for s in stages) else "failed"
        return PipelineResult(
            run_id=None,
            stages=stages,
            points=points,
            backtest=backtest_result,
            status=status,
        )

    def compare_models(
        self,
        base_load_mw: float,
        start: datetime,
        hours: int,
        seeds: list[int],
    ) -> dict[int, BacktestResult]:
        results: dict[int, BacktestResult] = {}
        for seed in seeds:
            points = self._engine.generate_hourly_demand(base_load_mw, start, hours, seed=seed)
            actuals = {
                p.timestamp: p.value_mw * Decimal("1.03")
                for p in points
            }
            results[seed] = self._engine.backtest(points, actuals)
        return results
