from __future__ import annotations

from uuid import uuid4

import pytest

from gridmind.core.types import ForecastHorizon, ForecastType
from gridmind.domains.forecasting.pipeline import ForecastPipeline


class TestForecastPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_generates_points(self) -> None:
        pipeline = ForecastPipeline()
        result = await pipeline.run(
            uuid4(), ForecastType.DEMAND, ForecastHorizon.HOURLY, hours=24, seed=42
        )
        assert result.status == "completed"
        assert len(result.points) == 24
        assert len(result.stages) >= 4

    @pytest.mark.asyncio
    async def test_pipeline_with_backtesting(self) -> None:
        from datetime import datetime, timezone
        from decimal import Decimal
        pipeline = ForecastPipeline()
        from gridmind.domains.forecasting.engine import ForecastEngine
        engine = ForecastEngine()
        start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        points = engine.generate_hourly_demand(1000, start, 12, seed=42)
        actuals = {p.timestamp: p.value_mw * Decimal("1.02") for p in points}
        result = await pipeline.run(
            uuid4(), ForecastType.DEMAND, ForecastHorizon.HOURLY,
            hours=12, historical_actuals=actuals, seed=42,
        )
        assert result.backtest is not None
        assert result.backtest.sample_count > 0
