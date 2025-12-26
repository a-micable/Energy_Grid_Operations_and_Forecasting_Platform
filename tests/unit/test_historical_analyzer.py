from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from gridmind.domains.analytics.historical import HistoricalAnalyzer, TimeSeriesPoint


def make_series(base: datetime, values: list[float]) -> list[TimeSeriesPoint]:
    return [
        TimeSeriesPoint(base + timedelta(hours=i), v)
        for i, v in enumerate(values)
    ]


class TestHistoricalAnalyzer:
    def setup_method(self) -> None:
        self.analyzer = HistoricalAnalyzer()
        self.base = datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)

    def test_summarize(self) -> None:
        points = make_series(self.base, [100, 200, 300, 400, 500])
        summary = self.analyzer.summarize(points)
        assert summary.count == 5
        assert summary.mean == 300
        assert summary.min == 100
        assert summary.max == 500

    def test_trend_increasing(self) -> None:
        points = make_series(self.base, list(range(100, 200, 5)))
        trend = self.analyzer.compute_trend(points)
        assert trend.direction == "increasing"
        assert trend.slope > 0

    def test_anomaly_detection(self) -> None:
        values = [100.0] * 30 + [500.0] + [100.0] * 10
        points = make_series(self.base, values)
        anomalies = self.analyzer.detect_anomalies(points, window_size=24)
        anomaly_flags = [a for a in anomalies if a.is_anomaly]
        assert len(anomaly_flags) >= 1

    def test_load_factor(self) -> None:
        points = make_series(self.base, [800, 850, 900, 850, 800])
        lf = self.analyzer.compute_load_factor(points, peak_capacity=1000)
        assert 0.8 <= lf <= 0.9

    def test_forecast_accuracy(self) -> None:
        forecast = make_series(self.base, [100, 110, 120])
        actual = make_series(self.base, [105, 108, 125])
        metrics = self.analyzer.forecast_accuracy_metrics(forecast, actual)
        assert metrics["count"] == 3
        assert metrics["mae"] > 0

    def test_peak_hours(self) -> None:
        values = []
        for h in range(24):
            values.extend([500 if 17 <= h <= 20 else 200])
        points = make_series(self.base, values[:24])
        peaks = self.analyzer.identify_peak_hours(points, top_n=3)
        assert len(peaks) == 3
        assert peaks[0]["hour"] in range(17, 21)

    def test_compare_periods(self) -> None:
        period_a = make_series(self.base, [100, 110, 120])
        period_b = make_series(self.base + timedelta(days=7), [130, 140, 150])
        comparison = self.analyzer.compare_periods(period_a, period_b)
        assert comparison["mean_change_pct"] > 0

    def test_rolling_statistics(self) -> None:
        points = make_series(self.base, list(range(100, 150)))
        rolling = self.analyzer.rolling_statistics(points, window=5)
        assert len(rolling) == len(points) - 5

    def test_ramp_rate(self) -> None:
        points = make_series(self.base, [100, 150, 200, 180])
        ramps = self.analyzer.compute_ramp_rate(points)
        assert len(ramps) == 3
        assert ramps[0]["ramp_rate_mw_per_hour"] == 50.0
