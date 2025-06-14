from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from gridmind.core.exceptions import ValidationError


def validate_uuid(value: Any, field_name: str = "id") -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise ValidationError(f"Invalid UUID for {field_name}: {value}") from exc


def validate_positive_decimal(value: Any, field_name: str) -> Decimal:
    d = Decimal(str(value))
    if d <= 0:
        raise ValidationError(f"{field_name} must be positive, got {d}")
    return d


def validate_non_negative_decimal(value: Any, field_name: str) -> Decimal:
    d = Decimal(str(value))
    if d < 0:
        raise ValidationError(f"{field_name} must be non-negative, got {d}")
    return d


def validate_time_range(start: datetime, end: datetime, *, field_name: str = "time range") -> None:
    if end <= start:
        raise ValidationError(f"Invalid {field_name}: end ({end}) must be after start ({start})")


def validate_code(value: str, *, pattern: str = r"^[A-Z0-9-]+$", max_length: int = 64) -> str:
    if not value or len(value) > max_length:
        raise ValidationError(f"Code must be 1-{max_length} characters")
    if not re.match(pattern, value):
        raise ValidationError(f"Code '{value}' does not match pattern {pattern}")
    return value


def validate_percentage(value: Any, field_name: str) -> Decimal:
    d = Decimal(str(value))
    if d < 0 or d > 1:
        raise ValidationError(f"{field_name} must be between 0 and 1, got {d}")
    return d


def validate_dispatch_priority(priority: int) -> int:
    if priority < 0 or priority > 1000:
        raise ValidationError(f"Dispatch priority must be 0-1000, got {priority}")
    return priority


def validate_forecast_horizon_hours(hours: int) -> int:
    if hours < 1 or hours > 168:
        raise ValidationError(f"Forecast horizon must be 1-168 hours, got {hours}")
    return hours


class RequestValidator:
    """Composite validator for API requests."""

    @staticmethod
    def validate_create_forecast(data: dict) -> dict:
        validate_uuid(data.get("zone_id"), "zone_id")
        validate_forecast_horizon_hours(data.get("hours", 48))
        if data.get("base_load_mw", 0) <= 0:
            raise ValidationError("base_load_mw must be positive")
        return data

    @staticmethod
    def validate_create_outage(data: dict) -> dict:
        validate_uuid(data.get("zone_id"), "zone_id")
        validate_time_range(data["planned_start"], data["planned_end"])
        if data.get("impact_mw", 0) < 0:
            raise ValidationError("impact_mw must be non-negative")
        return data

    @staticmethod
    def validate_dispatch_plan(data: dict) -> dict:
        validate_uuid(data.get("zone_id"), "zone_id")
        validate_time_range(data["horizon_start"], data["horizon_end"])
        validate_positive_decimal(data.get("demand_mw"), "demand_mw")
        if not data.get("resources"):
            raise ValidationError("At least one resource required")
        return data
