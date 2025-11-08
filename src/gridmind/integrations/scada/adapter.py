from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)


class SCADAPointType(StrEnum):
    ANALOG = "analog"
    DIGITAL = "digital"
    COUNTER = "counter"
    STRING = "string"


@dataclass
class SCADAPoint:
    point_id: str
    point_type: SCADAPointType
    value: Any
    quality: int
    timestamp: datetime
    unit: str = ""
    description: str = ""
    resource_id: str | None = None
    zone_id: str | None = None


@dataclass
class SCADASubscription:
    point_ids: list[str]
    callback_url: str | None = None
    poll_interval_seconds: int = 5
    active: bool = True


class SCADAProtocol(Protocol):
    async def connect(self) -> bool: ...
    async def disconnect(self) -> None: ...
    async def read_point(self, point_id: str) -> SCADAPoint: ...
    async def read_points(self, point_ids: list[str]) -> list[SCADAPoint]: ...
    async def write_point(self, point_id: str, value: Any) -> bool: ...


@dataclass
class SCADAConnectionConfig:
    host: str
    port: int
    protocol: str = "opcua"
    timeout_seconds: int = 30
    retry_count: int = 3
    credentials: dict[str, str] = field(default_factory=dict)


class SCADAAdapter:
    """Adapter for SCADA system integration with point mapping and validation."""

    QUALITY_GOOD = 192
    QUALITY_UNCERTAIN = 64
    QUALITY_BAD = 0

    POWER_POINT_SUFFIXES = ("_MW", "_KW", "_MVAR")
    STATUS_POINT_SUFFIXES = ("_STATUS", "_STATE", "_MODE")

    def __init__(self, config: SCADAConnectionConfig) -> None:
        self._config = config
        self._connected = False
        self._point_cache: dict[str, SCADAPoint] = {}
        self._subscriptions: dict[str, SCADASubscription] = {}
        self._point_mappings: dict[str, dict[str, str]] = {}

    async def connect(self) -> bool:
        logger.info("scada_connecting", host=self._config.host, port=self._config.port)
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False
        self._point_cache.clear()
        logger.info("scada_disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def register_point_mapping(self, resource_code: str, mappings: dict[str, str]) -> None:
        """Map resource codes to SCADA point IDs."""
        self._point_mappings[resource_code] = mappings

    def validate_point_quality(self, point: SCADAPoint) -> tuple[bool, list[str]]:
        issues: list[str] = []
        if point.quality < self.QUALITY_UNCERTAIN:
            issues.append(f"Bad quality: {point.quality}")
        if point.timestamp > datetime.now(timezone.utc):
            issues.append("Future timestamp")
        if point.point_type == SCADAPointType.ANALOG and isinstance(point.value, (int, float)):
            if point.value < 0 and any(point.point_id.endswith(s) for s in self.POWER_POINT_SUFFIXES):
                issues.append(f"Negative power reading: {point.value}")
        return len(issues) == 0, issues

    async def read_resource_output(self, resource_code: str) -> Decimal | None:
        mapping = self._point_mappings.get(resource_code, {})
        output_point = mapping.get("output_mw")
        if not output_point:
            logger.warning("scada_no_output_mapping", resource=resource_code)
            return None
        point = await self._read_point_simulated(output_point)
        valid, issues = self.validate_point_quality(point)
        if not valid:
            logger.warning("scada_invalid_point", point=output_point, issues=issues)
            return None
        return Decimal(str(point.value))

    async def read_zone_demand(self, zone_code: str) -> Decimal | None:
        mapping = self._point_mappings.get(zone_code, {})
        demand_point = mapping.get("demand_mw")
        if not demand_point:
            return None
        point = await self._read_point_simulated(demand_point)
        valid, _ = self.validate_point_quality(point)
        return Decimal(str(point.value)) if valid else None

    async def _read_point_simulated(self, point_id: str) -> SCADAPoint:
        if point_id in self._point_cache:
            cached = self._point_cache[point_id]
            age = (datetime.now(timezone.utc) - cached.timestamp).total_seconds()
            if age < 30:
                return cached
        import random
        value = random.uniform(800, 1200) if "MW" in point_id else random.randint(0, 1)
        point = SCADAPoint(
            point_id=point_id,
            point_type=SCADAPointType.ANALOG,
            value=round(value, 2),
            quality=self.QUALITY_GOOD,
            timestamp=datetime.now(timezone.utc),
            unit="MW" if "MW" in point_id else "",
        )
        self._point_cache[point_id] = point
        return point

    async def read_all_subscribed(self) -> dict[str, list[SCADAPoint]]:
        results: dict[str, list[SCADAPoint]] = {}
        for sub_id, sub in self._subscriptions.items():
            if not sub.active:
                continue
            points = []
            for pid in sub.point_ids:
                point = await self._read_point_simulated(pid)
                points.append(point)
            results[sub_id] = points
        return results

    def add_subscription(self, sub_id: str, subscription: SCADASubscription) -> None:
        self._subscriptions[sub_id] = subscription

    def remove_subscription(self, sub_id: str) -> None:
        self._subscriptions.pop(sub_id, None)

    async def write_dispatch_setpoint(
        self, resource_code: str, target_mw: Decimal
    ) -> bool:
        mapping = self._point_mappings.get(resource_code, {})
        setpoint_point = mapping.get("setpoint_mw")
        if not setpoint_point:
            logger.error("scada_no_setpoint_mapping", resource=resource_code)
            return False
        logger.info(
            "scada_write_setpoint",
            resource=resource_code,
            point=setpoint_point,
            value=str(target_mw),
        )
        return True

    def get_cache_stats(self) -> dict[str, Any]:
        return {
            "cached_points": len(self._point_cache),
            "active_subscriptions": sum(1 for s in self._subscriptions.values() if s.active),
            "mapped_resources": len(self._point_mappings),
            "connected": self._connected,
        }
