from __future__ import annotations

import pytest

from gridmind.core.types import ForecastHorizon, ForecastType
from gridmind.domains.forecasting.service import ForecastingService


@pytest.mark.asyncio
async def test_create_forecast_run(db_session, sample_zone) -> None:
    service = ForecastingService(db_session)
    run = await service.create_forecast_run(
        sample_zone.id,
        ForecastType.DEMAND,
        ForecastHorizon.HOURLY,
        base_load_mw=1500.0,
        hours=24,
    )
    assert run.status == "completed"
    assert run.metrics.get("point_count") == 24


@pytest.mark.asyncio
async def test_revise_forecast_creates_new_version(db_session, sample_zone) -> None:
    service = ForecastingService(db_session)
    run = await service.create_forecast_run(
        sample_zone.id,
        ForecastType.DEMAND,
        ForecastHorizon.HOURLY,
        hours=12,
    )
    from gridmind.db.repositories.forecasting import ForecastVersionRepository
    version_repo = ForecastVersionRepository(db_session)
    current = await version_repo.get_current_for_run(run.id)
    assert current is not None

    from gridmind.domains.forecasting.engine import ForecastEngine
    engine = ForecastEngine()
    from datetime import datetime, timezone
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    revised = engine.generate_hourly_demand(1550.0, start, 12, seed=99)

    new_version = await service.revise_forecast(
        run.id, revised, reason="Updated load assumptions", revised_by="forecaster@grid.com"
    )
    assert new_version.version_number == 2
    assert not current.is_current
