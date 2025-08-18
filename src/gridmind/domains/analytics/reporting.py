from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from gridmind.domains.analytics.historical import HistoricalAnalyzer, TimeSeriesPoint


@dataclass
class OperationalReport:
    report_id: str
    report_type: str
    period_start: datetime
    period_end: datetime
    sections: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)


class OperationalReportGenerator:
    """Generate operational reports from historical data."""

    def __init__(self) -> None:
        self._analyzer = HistoricalAnalyzer()

    def generate_daily_operations_report(
        self,
        demand_points: list[TimeSeriesPoint],
        supply_points: list[TimeSeriesPoint],
        period_start: datetime,
        period_end: datetime,
    ) -> OperationalReport:
        demand_summary = self._analyzer.summarize(demand_points)
        supply_summary = self._analyzer.summarize(supply_points)
        demand_trend = self._analyzer.compute_trend(demand_points)
        anomalies = self._analyzer.detect_anomalies(demand_points)
        peak_hours = self._analyzer.identify_peak_hours(demand_points)
        recommendations: list[str] = []
        if demand_summary.max > demand_summary.mean * 1.5:
            recommendations.append("Consider increasing reserve capacity for peak hours")
        if len([a for a in anomalies if a.is_anomaly]) > 5:
            recommendations.append("Investigate demand anomalies detected during period")
        if demand_trend.direction == "increasing":
            recommendations.append("Upward demand trend detected - review capacity planning")
        return OperationalReport(
            report_id=f"DAILY-{period_start.strftime('%Y%m%d')}",
            report_type="daily_operations",
            period_start=period_start,
            period_end=period_end,
            sections={
                "demand_summary": {
                    "mean_mw": demand_summary.mean,
                    "peak_mw": demand_summary.max,
                    "min_mw": demand_summary.min,
                    "std_mw": demand_summary.std,
                },
                "supply_summary": {
                    "mean_mw": supply_summary.mean,
                    "peak_mw": supply_summary.max,
                },
                "demand_trend": {
                    "direction": demand_trend.direction,
                    "change_pct": demand_trend.change_pct,
                    "r_squared": demand_trend.r_squared,
                },
                "anomaly_count": len([a for a in anomalies if a.is_anomaly]),
                "peak_hours": peak_hours,
                "load_factor": self._analyzer.compute_load_factor(
                    demand_points, demand_summary.max
                ),
            },
            recommendations=recommendations,
        )

    def generate_forecast_accuracy_report(
        self,
        forecast_points: list[TimeSeriesPoint],
        actual_points: list[TimeSeriesPoint],
        period_start: datetime,
        period_end: datetime,
    ) -> OperationalReport:
        metrics = self._analyzer.forecast_accuracy_metrics(forecast_points, actual_points)
        recommendations: list[str] = []
        if metrics.get("mape", 0) > 0.10:
            recommendations.append("Forecast MAPE exceeds 10% - model recalibration recommended")
        if abs(metrics.get("bias", 0)) > 50:
            direction = "over" if metrics["bias"] < 0 else "under"
            recommendations.append(f"Systematic {direction}-forecasting bias detected")
        return OperationalReport(
            report_id=f"FORECAST-ACC-{period_start.strftime('%Y%m%d')}",
            report_type="forecast_accuracy",
            period_start=period_start,
            period_end=period_end,
            sections={"accuracy_metrics": metrics},
            recommendations=recommendations,
        )
