from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gridmind.db.base import Base
from gridmind.db.models.grid import GenerationResource, GridZone


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def sample_zone(db_session: AsyncSession) -> GridZone:
    zone = GridZone(
        code="ZONE-NORTH-01",
        name="Northern Grid Zone",
        region="North",
        peak_demand_mw=Decimal("2500.000"),
    )
    db_session.add(zone)
    await db_session.flush()
    return zone


@pytest_asyncio.fixture
async def sample_resources(db_session: AsyncSession, sample_zone: GridZone) -> list[GenerationResource]:
    resources = [
        GenerationResource(
            zone_id=sample_zone.id,
            code="GAS-001",
            name="North Gas Plant",
            resource_type="gas_plant",
            capacity_mw=Decimal("500"),
            marginal_cost_per_mwh=Decimal("45.50"),
            emission_rate_kg_co2_per_mwh=Decimal("400"),
            dispatch_priority=50,
        ),
        GenerationResource(
            zone_id=sample_zone.id,
            code="SOLAR-001",
            name="North Solar Farm",
            resource_type="solar_farm",
            capacity_mw=Decimal("200"),
            marginal_cost_per_mwh=Decimal("0"),
            is_renewable=True,
            dispatch_priority=10,
        ),
        GenerationResource(
            zone_id=sample_zone.id,
            code="WIND-001",
            name="North Wind Farm",
            resource_type="wind_farm",
            capacity_mw=Decimal("300"),
            marginal_cost_per_mwh=Decimal("0"),
            is_renewable=True,
            dispatch_priority=20,
        ),
    ]
    db_session.add_all(resources)
    await db_session.flush()
    return resources
