from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from gridmind.core.exceptions import ForecastDriftError, ValidationError
from gridmind.core.types import ForecastType
from gridmind.domains.forecasting.engine import ForecastEngine, ForecastPointData


class TestForecastEngine:
    def setup_method(self) -> None:
        self.engine = ForecastEngine(drift_threshold_pct=Decimal("0.15"))

    def test_generate_hourly_demand_produces_expected_points(self) -> None:
        start = datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)
        points = self.engine.generate_hourly_demand(1000.0, start, 24, seed=42)
        assert len(points) == 24
        assert all(p.value_mw > 0 for p in points)
        assert all(p.lower_bound_mw is not None for p in points)

    def test_generate_solar_output_zero_at_night(self) -> None:
        start = datetime(2025, 6, 21, 0, 0, tzinfo=timezone.utc)
        points = self.engine.generate_renewable_output(
            100.0, ForecastType.SOLAR, start, 24, seed=42
        )
        night_points = [p for p in points if p.timestamp.hour < 6 or p.timestamp.hour > 20]
        assert all(float(p.value_mw) == 0.0 for p in night_points)

    def test_revision_delta_computation(self) -> None:
        start = datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)
        original = self.engine.generate_hourly_demand(1000.0, start, 10, seed=42)
        revised = [
            ForecastPointData(
                timestamp=p.timestamp,
                value_mw=p.value_mw * Decimal("1.02"),
            )
            for p in original
        ]
        delta = self.engine.compute_revision_delta(original, revised)
        assert Decimal("0.01") < delta < Decimal("0.03")

    def test_drift_detection_raises_on_large_revision(self) -> None:
        start = datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)
        original = self.engine.generate_hourly_demand(1000.0, start, 10, seed=42)
        revised = [
            ForecastPointData(
                timestamp=p.timestamp,
                value_mw=p.value_mw * Decimal("1.50"),
            )
            for p in original
        ]
        with pytest.raises(ForecastDriftError):
            self.engine.validate_revision(uuid4(), original, revised)

    def test_backtest_computes_metrics(self) -> None:
        start = datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)
        points = self.engine.generate_hourly_demand(1000.0, start, 10, seed=42)
        actuals = {p.timestamp: p.value_mw * Decimal("1.05") for p in points}
        result = self.engine.backtest(points, actuals)
        assert result.sample_count == 10
        assert result.mae > 0
        assert result.rmse >= result.mae

    def test_mismatched_revision_points_raises(self) -> None:
        start = datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)
        original = self.engine.generate_hourly_demand(1000.0, start, 10, seed=42)
        with pytest.raises(ValidationError):
            self.engine.compute_revision_delta(original, original[:5])
