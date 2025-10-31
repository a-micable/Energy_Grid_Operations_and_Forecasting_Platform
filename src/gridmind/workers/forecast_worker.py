from __future__ import annotations

import structlog

from gridmind.db.session import session_scope
from gridmind.domains.forecasting.service import ForecastingService
from gridmind.workers.base import Worker

logger = structlog.get_logger(__name__)


class ForecastWorker(Worker):
    """Background worker for scheduled forecast generation."""

    name = "forecast_worker"
    poll_interval_seconds = 60.0

    def __init__(self, zone_configs: list[dict] | None = None) -> None:
        super().__init__()
        self._zone_configs = zone_configs or []

    async def process_batch(self) -> int:
        processed = 0
        async with session_scope() as session:
            service = ForecastingService(session)
            for config in self._zone_configs:
                try:
                    from gridmind.core.types import ForecastHorizon, ForecastType
                    from uuid import UUID
                    await service.create_forecast_run(
                        UUID(config["zone_id"]),
                        ForecastType(config["forecast_type"]),
                        ForecastHorizon(config["horizon"]),
                        base_load_mw=config.get("base_load_mw", 1500.0),
                        hours=config.get("hours", 48),
                    )
                    processed += 1
                except Exception:
                    logger.exception("forecast_generation_failed", zone=config.get("zone_id"))
        return processed
