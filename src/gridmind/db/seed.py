from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.db.models.grid import GenerationResource, GridZone


async def seed_development_data(session: AsyncSession) -> dict:
    """Seed development database with realistic grid topology."""
    zones = [
        GridZone(code="NORTH-01", name="Northern Zone", region="North", peak_demand_mw=Decimal("3200")),
        GridZone(code="SOUTH-01", name="Southern Zone", region="South", peak_demand_mw=Decimal("2800")),
        GridZone(code="CENTRAL-01", name="Central Zone", region="Central", peak_demand_mw=Decimal("4500")),
    ]
    session.add_all(zones)
    await session.flush()

    resources: list[GenerationResource] = []
    for zone in zones:
        resources.extend([
            GenerationResource(
                zone_id=zone.id, code=f"{zone.code}-GAS-01", name=f"{zone.name} Gas Plant",
                resource_type="gas_plant", capacity_mw=Decimal("500"),
                marginal_cost_per_mwh=Decimal("45"), emission_rate_kg_co2_per_mwh=Decimal("400"),
                dispatch_priority=60,
            ),
            GenerationResource(
                zone_id=zone.id, code=f"{zone.code}-SOLAR-01", name=f"{zone.name} Solar",
                resource_type="solar_farm", capacity_mw=Decimal("200"),
                marginal_cost_per_mwh=Decimal("0"), is_renewable=True, dispatch_priority=10,
            ),
            GenerationResource(
                zone_id=zone.id, code=f"{zone.code}-WIND-01", name=f"{zone.name} Wind",
                resource_type="wind_farm", capacity_mw=Decimal("300"),
                marginal_cost_per_mwh=Decimal("0"), is_renewable=True, dispatch_priority=15,
            ),
        ])
    session.add_all(resources)
    await session.flush()
    return {"zones": len(zones), "resources": len(resources)}
