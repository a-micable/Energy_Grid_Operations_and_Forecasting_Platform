from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from gridmind.domains.events.ingestion import SensorEventIngester, SensorReading, SensorType


class TestSensorIngestion:
    def setup_method(self) -> None:
        self.ingester = SensorEventIngester()

    def test_valid_reading_accepted(self) -> None:
        reading = SensorReading(
            sensor_id="SCADA-001",
            sensor_type=SensorType.SCADA,
            timestamp=datetime.now(timezone.utc),
            value=Decimal("1500.5"),
            unit="MW",
            quality_flag=95,
        )
        accepted, issues = self.ingester.ingest(reading)
        assert accepted
        assert len(issues) == 0

    def test_negative_power_rejected(self) -> None:
        reading = SensorReading(
            sensor_id="SCADA-002",
            sensor_type=SensorType.SCADA,
            timestamp=datetime.now(timezone.utc),
            value=Decimal("-100"),
            unit="MW",
            quality_flag=95,
        )
        accepted, issues = self.ingester.ingest(reading)
        assert not accepted

    def test_aggregate_readings(self) -> None:
        base = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        readings = [
            SensorReading("S1", SensorType.SCADa, base, Decimal("100"), "MW", 90),
            SensorReading("S1", SensorType.SCADA, base.replace(minute=1), Decimal("102"), "MW", 92),
        ]
        # Fix enum typo in test
        readings[0] = SensorReading("S1", SensorType.SCADA, base, Decimal("100"), "MW", 90)
        aggregated = self.ingester.aggregate_readings(readings, interval_seconds=300)
        assert len(aggregated) == 1
        assert aggregated[0].value == Decimal("101")
