from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from gridmind.core.exceptions import ValidationError
from gridmind.core.validation import (
    RequestValidator,
    validate_code,
    validate_percentage,
    validate_time_range,
    validate_uuid,
)


class TestValidation:
    def test_validate_uuid_accepts_string(self) -> None:
        uid = uuid4()
        assert validate_uuid(str(uid)) == uid

    def test_validate_uuid_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            validate_uuid("not-a-uuid")

    def test_validate_time_range(self) -> None:
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 2, tzinfo=timezone.utc)
        validate_time_range(start, end)

    def test_validate_time_range_rejects_inverted(self) -> None:
        with pytest.raises(ValidationError):
            validate_time_range(
                datetime(2025, 1, 2, tzinfo=timezone.utc),
                datetime(2025, 1, 1, tzinfo=timezone.utc),
            )

    def test_validate_code(self) -> None:
        assert validate_code("ZONE-01") == "ZONE-01"

    def test_validate_code_rejects_lowercase(self) -> None:
        with pytest.raises(ValidationError):
            validate_code("zone-01")

    def test_validate_percentage(self) -> None:
        from decimal import Decimal
        assert validate_percentage("0.95", "confidence") == Decimal("0.95")

    def test_request_validator_forecast(self) -> None:
        data = {"zone_id": str(uuid4()), "hours": 48, "base_load_mw": 1500}
        RequestValidator.validate_create_forecast(data)
