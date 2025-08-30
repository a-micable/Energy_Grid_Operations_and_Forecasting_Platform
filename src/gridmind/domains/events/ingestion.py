from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


class SensorType(StrEnum):
    SCADA = "scada"
    PMU = "pmu"
    SMART_METER = "smart_meter"
    WEATHER = "weather"
    MARKET = "market"


@dataclass
class SensorReading:
    sensor_id: str
    sensor_type: SensorType
    timestamp: datetime
    value: Decimal
    unit: str
    quality_flag: int = 0
    zone_id: UUID | None = None
    resource_id: UUID | None = None
    metadata: dict[str, Any] | None = None


class SensorEventIngester:
    """Ingest and validate sensor readings from SCADA and field devices."""

    QUALITY_THRESHOLD = 50

    def __init__(self) -> None:
        self._last_readings: dict[str, SensorReading] = {}
        self._anomaly_count: dict[str, int] = {}

    def validate_reading(self, reading: SensorReading) -> list[str]:
        issues: list[str] = []
        if reading.quality_flag < self.QUALITY_THRESHOLD:
            issues.append(f"Low quality flag: {reading.quality_flag}")
        if reading.value < 0 and reading.unit in ("MW", "MWh", "kW"):
            issues.append(f"Negative value for power reading: {reading.value}")
        if reading.timestamp > datetime.now(timezone.utc):
            issues.append("Future timestamp detected")
        last = self._last_readings.get(reading.sensor_id)
        if last:
            time_delta = (reading.timestamp - last.timestamp).total_seconds()
            if time_delta > 0:
                value_delta = abs(float(reading.value) - float(last.value))
                rate = value_delta / time_delta * 3600
                if rate > 1000 and reading.unit == "MW":
                    issues.append(f"Anomalous rate of change: {rate:.1f} MW/hour")
        return issues

    def ingest(self, reading: SensorReading) -> tuple[bool, list[str]]:
        issues = self.validate_reading(reading)
        if issues:
            self._anomaly_count[reading.sensor_id] = self._anomaly_count.get(reading.sensor_id, 0) + 1
            logger.warning(
                "sensor_reading_issues",
                sensor_id=reading.sensor_id,
                issues=issues,
            )
            if any("Negative" in i or "Future" in i for i in issues):
                return False, issues
        self._last_readings[reading.sensor_id] = reading
        return True, issues

    def to_domain_event_payload(self, reading: SensorReading) -> dict[str, Any]:
        return {
            "sensor_id": reading.sensor_id,
            "sensor_type": reading.sensor_type.value,
            "timestamp": reading.timestamp.isoformat(),
            "value": str(reading.value),
            "unit": reading.unit,
            "quality_flag": reading.quality_flag,
            "zone_id": str(reading.zone_id) if reading.zone_id else None,
            "resource_id": str(reading.resource_id) if reading.resource_id else None,
        }

    def aggregate_readings(
        self, readings: list[SensorReading], interval_seconds: int = 300
    ) -> list[SensorReading]:
        if not readings:
            return []
        sorted_readings = sorted(readings, key=lambda r: r.timestamp)
        buckets: dict[int, list[SensorReading]] = {}
        for r in sorted_readings:
            bucket_key = int(r.timestamp.timestamp()) // interval_seconds
            buckets.setdefault(bucket_key, []).append(r)
        aggregated: list[SensorReading] = []
        for bucket_readings in buckets.values():
            avg_value = sum(float(r.value) for r in bucket_readings) / len(bucket_readings)
            rep = bucket_readings[0]
            aggregated.append(
                SensorReading(
                    sensor_id=rep.sensor_id,
                    sensor_type=rep.sensor_type,
                    timestamp=bucket_readings[-1].timestamp,
                    value=Decimal(str(round(avg_value, 4))),
                    unit=rep.unit,
                    quality_flag=min(r.quality_flag for r in bucket_readings),
                    zone_id=rep.zone_id,
                    resource_id=rep.resource_id,
                )
            )
        return aggregated
