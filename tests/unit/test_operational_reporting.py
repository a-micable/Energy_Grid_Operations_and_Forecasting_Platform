from __future__ import annotations

from datetime import datetime, timezone

from gridmind.domains.analytics.historical import TimeSeriesPoint
from gridmind.domains.analytics.reporting import OperationalReportGenerator


class TestOperationalReportGenerator:
    def setup_method(self) -> None:
        self.generator = OperationalReportGenerator()
        self.start = datetime(2025, 7, 1, tzinfo=timezone.utc)
        self.end = datetime(2025, 7, 2, tzinfo=timezone.utc)

    def test_daily_operations_report(self) -> None:
        demand = [TimeSeriesPoint(self.start, 2000 + i * 50) for i in range(24)]
        supply = [TimeSeriesPoint(self.start, 1950 + i * 50) for i in range(24)]
        report = self.generator.generate_daily_operations_report(
            demand, supply, self.start, self.end
        )
        assert report.report_type == "daily_operations"
        assert "demand_summary" in report.sections
        assert report.sections["demand_summary"]["peak_mw"] > 0

    def test_forecast_accuracy_report(self) -> None:
        forecast = [TimeSeriesPoint(self.start, 1000 + i * 10) for i in range(24)]
        actual = [TimeSeriesPoint(self.start, 1020 + i * 10) for i in range(24)]
        report = self.generator.generate_forecast_accuracy_report(
            forecast, actual, self.start, self.end
        )
        assert "accuracy_metrics" in report.sections
        assert report.sections["accuracy_metrics"]["count"] == 24
