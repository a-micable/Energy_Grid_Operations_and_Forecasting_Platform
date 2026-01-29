"""Realistic grid test fixtures based on operational scenarios."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from gridmind.db.models.grid import GenerationResource, GridZone


def create_north_zone() -> GridZone:
    return GridZone(
        id=uuid4(),
        code="NORTH-01",
        name="Northern Metropolitan Zone",
        region="North",
        timezone="America/Chicago",
        peak_demand_mw=Decimal("3200.000"),
    )


def create_south_zone() -> GridZone:
    return GridZone(
        id=uuid4(),
        code="SOUTH-01",
        name="Southern Coastal Zone",
        region="South",
        timezone="America/Chicago",
        peak_demand_mw=Decimal("2800.000"),
    )


def create_north_resources(zone_id: UUID) -> list[GenerationResource]:
    return [
        GenerationResource(
            id=uuid4(), zone_id=zone_id, code="N-GAS-01",
            name="North Combined Cycle Gas", resource_type="gas_plant",
            capacity_mw=Decimal("850"), min_output_mw=Decimal("200"),
            marginal_cost_per_mwh=Decimal("42.50"), emission_rate_kg_co2_per_mwh=Decimal("380"),
            dispatch_priority=60, ramp_rate_mw_per_min=Decimal("15"),
        ),
        GenerationResource(
            id=uuid4(), zone_id=zone_id, code="N-GAS-02",
            name="North Peaker Gas", resource_type="gas_plant",
            capacity_mw=Decimal("300"), min_output_mw=Decimal("50"),
            marginal_cost_per_mwh=Decimal("85.00"), emission_rate_kg_co2_per_mwh=Decimal("450"),
            dispatch_priority=200, ramp_rate_mw_per_min=Decimal("30"),
        ),
        GenerationResource(
            id=uuid4(), zone_id=zone_id, code="N-SOLAR-01",
            name="North Solar Array", resource_type="solar_farm",
            capacity_mw=Decimal("250"), marginal_cost_per_mwh=Decimal("0"),
            dispatch_priority=5, is_renewable=True, ramp_rate_mw_per_min=Decimal("50"),
        ),
        GenerationResource(
            id=uuid4(), zone_id=zone_id, code="N-WIND-01",
            name="North Ridge Wind", resource_type="wind_farm",
            capacity_mw=Decimal("400"), marginal_cost_per_mwh=Decimal("0"),
            dispatch_priority=8, is_renewable=True, ramp_rate_mw_per_min=Decimal("20"),
        ),
        GenerationResource(
            id=uuid4(), zone_id=zone_id, code="N-HYDRO-01",
            name="North River Hydro", resource_type="hydro_plant",
            capacity_mw=Decimal("150"), min_output_mw=Decimal("20"),
            marginal_cost_per_mwh=Decimal("15.00"), emission_rate_kg_co2_per_mwh=Decimal("0"),
            dispatch_priority=15, is_renewable=True, ramp_rate_mw_per_min=Decimal("10"),
        ),
        GenerationResource(
            id=uuid4(), zone_id=zone_id, code="N-BESS-01",
            name="North Battery Storage", resource_type="battery",
            capacity_mw=Decimal("100"), marginal_cost_per_mwh=Decimal("25.00"),
            dispatch_priority=30, ramp_rate_mw_per_min=Decimal("50"),
        ),
    ]


def hourly_demand_profile(base_date: datetime | None = None) -> list[tuple[datetime, float]]:
    base = base_date or datetime(2025, 7, 15, 0, 0, tzinfo=timezone.utc)
    profile: list[tuple[datetime, float]] = []
    for h in range(24):
        ts = base + timedelta(hours=h)
        if 0 <= h < 6:
            load = 1800
        elif 6 <= h < 9:
            load = 2200 + (h - 6) * 200
        elif 9 <= h < 17:
            load = 2800
        elif 17 <= h < 21:
            load = 3200
        else:
            load = 2400 - (h - 21) * 100
        profile.append((ts, load))
    return profile


def solar_generation_profile(base_date: datetime | None = None, capacity: float = 250) -> list[tuple[datetime, float]]:
    base = base_date or datetime(2025, 7, 15, 0, 0, tzinfo=timezone.utc)
    import math
    profile: list[tuple[datetime, float]] = []
    for h in range(24):
        ts = base + timedelta(hours=h)
        if 6 <= h <= 20:
            factor = math.sin((h - 6) * math.pi / 14)
            output = capacity * factor
        else:
            output = 0.0
        profile.append((ts, output))
    return profile


OPERATIONAL_SCENARIOS = {
    "summer_peak": {
        "demand_mw": 3200,
        "renewable_pct": 0.35,
        "reserve_margin": 0.12,
        "description": "High demand summer afternoon peak",
    },
    "winter_storm": {
        "demand_mw": 2900,
        "renewable_pct": 0.15,
        "reserve_margin": 0.08,
        "description": "Winter storm with reduced renewable output",
    },
    "spring_maintenance": {
        "demand_mw": 2200,
        "renewable_pct": 0.45,
        "reserve_margin": 0.18,
        "description": "Spring shoulder season with planned maintenance",
    },
    "emergency_outage": {
        "demand_mw": 3000,
        "renewable_pct": 0.25,
        "reserve_margin": 0.05,
        "description": "Emergency gas plant outage scenario",
    },
}
