from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import NewType, TypeVar
from uuid import UUID

ResourceId = NewType("ResourceId", UUID)
ForecastId = NewType("ForecastId", UUID)
OutageId = NewType("OutageId", UUID)
DispatchId = NewType("DispatchId", UUID)
EventId = NewType("EventId", UUID)
AuditId = NewType("AuditId", UUID)
GridZoneId = NewType("GridZoneId", UUID)

T = TypeVar("T")


class ResourceType(StrEnum):
    GAS_PLANT = "gas_plant"
    SOLAR_FARM = "solar_farm"
    WIND_FARM = "wind_farm"
    HYDRO_PLANT = "hydro_plant"
    BATTERY = "battery"
    IMPORT = "import"


class ForecastHorizon(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class ForecastType(StrEnum):
    DEMAND = "demand"
    RENEWABLE = "renewable"
    SOLAR = "solar"
    WIND = "wind"


class BalancingMode(StrEnum):
    REALTIME = "realtime"
    SCHEDULED = "scheduled"
    EMERGENCY = "emergency"


class OutageType(StrEnum):
    PLANNED = "planned"
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"


class OutageStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DispatchStatus(StrEnum):
    PENDING = "pending"
    OPTIMIZING = "optimizing"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class BatteryState(StrEnum):
    IDLE = "idle"
    CHARGING = "charging"
    DISCHARGING = "discharging"
    EMERGENCY_DISCHARGE = "emergency_discharge"
    MAINTENANCE = "maintenance"


class PowerMW(Decimal):
    """Megawatt power quantity with validation."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: object) -> PowerMW:
        if isinstance(v, cls):
            return v
        d = Decimal(str(v))
        if d < 0:
            raise ValueError("Power cannot be negative")
        return cls(d)


class EnergyMWh(Decimal):
    """Megawatt-hour energy quantity."""

    @classmethod
    def validate(cls, v: object) -> EnergyMWh:
        d = Decimal(str(v))
        if d < 0:
            raise ValueError("Energy cannot be negative")
        return cls(d)


class Timestamped:
    created_at: datetime
    updated_at: datetime
