from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Sequence

import numpy as np


@dataclass
class TimeSeriesPoint:
    timestamp: datetime
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StatisticalSummary:
    count: int
    mean: float
    std: float
    min: float
    max: float
    median: float
    p25: float
    p75: float
    p95: float
    p99: float


@dataclass
class TrendAnalysis:
    slope: float
    intercept: float
    r_squared: float
    direction: str
    change_pct: float


@dataclass
class AnomalyDetectionResult:
    timestamp: datetime
    value: float
    expected: float
    deviation: float
    severity: str
    is_anomaly: bool


class HistoricalAnalyzer:
    """Analyze historical grid operational data for patterns and anomalies."""

    ANOMALY_THRESHOLD_STD = 2.5

    def summarize(self, points: Sequence[TimeSeriesPoint]) -> StatisticalSummary:
        if not points:
            return StatisticalSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        values = np.array([p.value for p in points])
        return StatisticalSummary(
            count=len(values),
            mean=float(np.mean(values)),
            std=float(np.std(values)),
            min=float(np.min(values)),
            max=float(np.max(values)),
            median=float(np.median(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
        )

    def compute_trend(self, points: Sequence[TimeSeriesPoint]) -> TrendAnalysis:
        if len(points) < 2:
            return TrendAnalysis(0, 0, 0, "stable", 0)
        base_time = points[0].timestamp.timestamp()
        x = np.array([(p.timestamp.timestamp() - base_time) / 3600 for p in points])
        y = np.array([p.value for p in points])
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = float(coeffs[0]), float(coeffs[1])
        predicted = slope * x + intercept
        ss_res = np.sum((y - predicted) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0
        change_pct = (slope * (x[-1] - x[0]) / y[0] * 100) if y[0] != 0 else 0
        direction = "increasing" if slope > 0.01 else "decreasing" if slope < -0.01 else "stable"
        return TrendAnalysis(slope, intercept, r_squared, direction, change_pct)

    def detect_anomalies(
        self, points: Sequence[TimeSeriesPoint], *, window_size: int = 24
    ) -> list[AnomalyDetectionResult]:
        if len(points) < window_size:
            return []
        results: list[AnomalyDetectionResult] = []
        values = [p.value for p in points]
        for i in range(window_size, len(points)):
            window = values[i - window_size:i]
            mean = np.mean(window)
            std = np.std(window)
            if std == 0:
                continue
            deviation = (values[i] - mean) / std
            is_anomaly = abs(deviation) > self.ANOMALY_THRESHOLD_STD
            severity = "critical" if abs(deviation) > 4 else "warning" if is_anomaly else "normal"
            results.append(AnomalyDetectionResult(
                timestamp=points[i].timestamp,
                value=values[i],
                expected=mean,
                deviation=float(deviation),
                severity=severity,
                is_anomaly=is_anomaly,
            ))
        return results

    def compute_load_factor(self, points: Sequence[TimeSeriesPoint], peak_capacity: float) -> float:
        if not points or peak_capacity <= 0:
            return 0.0
        avg_load = np.mean([p.value for p in points])
        return float(avg_load / peak_capacity)

    def compute_peak_to_average_ratio(self, points: Sequence[TimeSeriesPoint]) -> float:
        if not points:
            return 0.0
        values = [p.value for p in points]
        return max(values) / np.mean(values) if np.mean(values) > 0 else 0

    def seasonal_decomposition(
        self, points: Sequence[TimeSeriesPoint], period: int = 24
    ) -> dict[str, list[float]]:
        if len(points) < period * 2:
            return {"trend": [], "seasonal": [], "residual": []}
        values = np.array([p.value for p in points])
        n = len(values)
        trend = np.convolve(values, np.ones(period) / period, mode="valid")
        detrended = values[period - 1:]
        seasonal = np.zeros(min(len(detrended), period))
        for i in range(period):
            indices = list(range(i, len(detrended), period))
            if indices:
                seasonal[i % period] = np.mean([detrended[j] for j in indices if j < len(detrended)])
        residual = detrended[: len(seasonal)] - seasonal[: len(detrended)]
        return {
            "trend": trend.tolist(),
            "seasonal": seasonal.tolist(),
            "residual": residual.tolist() if hasattr(residual, "tolist") else list(residual),
        }

    def compare_periods(
        self,
        period_a: Sequence[TimeSeriesPoint],
        period_b: Sequence[TimeSeriesPoint],
    ) -> dict[str, Any]:
        summary_a = self.summarize(period_a)
        summary_b = self.summarize(period_b)
        return {
            "period_a": {"mean": summary_a.mean, "max": summary_a.max, "count": summary_a.count},
            "period_b": {"mean": summary_b.mean, "max": summary_b.max, "count": summary_b.count},
            "mean_change_pct": ((summary_b.mean - summary_a.mean) / summary_a.mean * 100)
            if summary_a.mean else 0,
            "max_change_pct": ((summary_b.max - summary_a.max) / summary_a.max * 100)
            if summary_a.max else 0,
            "volatility_change": summary_b.std - summary_a.std,
        }

    def forecast_accuracy_metrics(
        self,
        forecast: Sequence[TimeSeriesPoint],
        actual: Sequence[TimeSeriesPoint],
    ) -> dict[str, float]:
        actual_map = {p.timestamp: p.value for p in actual}
        errors: list[float] = []
        pct_errors: list[float] = []
        for fp in forecast:
            act = actual_map.get(fp.timestamp)
            if act is None:
                continue
            error = act - fp.value
            errors.append(error)
            if act != 0:
                pct_errors.append(abs(error) / act)
        if not errors:
            return {"mae": 0, "rmse": 0, "mape": 0, "bias": 0, "count": 0}
        arr = np.array(errors)
        return {
            "mae": float(np.mean(np.abs(arr))),
            "rmse": float(np.sqrt(np.mean(arr**2))),
            "mape": float(np.mean(pct_errors)) if pct_errors else 0,
            "bias": float(np.mean(arr)),
            "count": len(errors),
        }

    def rolling_statistics(
        self, points: Sequence[TimeSeriesPoint], window: int = 12
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        values = [p.value for p in points]
        for i in range(window, len(points)):
            window_vals = values[i - window:i]
            results.append({
                "timestamp": points[i].timestamp.isoformat(),
                "mean": float(np.mean(window_vals)),
                "std": float(np.std(window_vals)),
                "min": float(np.min(window_vals)),
                "max": float(np.max(window_vals)),
            })
        return results

    def identify_peak_hours(
        self, points: Sequence[TimeSeriesPoint], top_n: int = 5
    ) -> list[dict[str, Any]]:
        hourly: dict[int, list[float]] = {}
        for p in points:
            hourly.setdefault(p.timestamp.hour, []).append(p.value)
        hourly_avg = {h: np.mean(vals) for h, vals in hourly.items()}
        sorted_hours = sorted(hourly_avg.items(), key=lambda x: x[1], reverse=True)
        return [
            {"hour": h, "avg_load_mw": float(avg), "rank": i + 1}
            for i, (h, avg) in enumerate(sorted_hours[:top_n])
        ]

    def compute_ramp_rate(
        self, points: Sequence[TimeSeriesPoint]
    ) -> list[dict[str, Any]]:
        ramps: list[dict[str, Any]] = []
        for i in range(1, len(points)):
            dt_hours = (points[i].timestamp - points[i - 1].timestamp).total_seconds() / 3600
            if dt_hours <= 0:
                continue
            ramp = (points[i].value - points[i - 1].value) / dt_hours
            ramps.append({
                "timestamp": points[i].timestamp.isoformat(),
                "ramp_rate_mw_per_hour": float(ramp),
                "duration_hours": dt_hours,
            })
        return ramps
