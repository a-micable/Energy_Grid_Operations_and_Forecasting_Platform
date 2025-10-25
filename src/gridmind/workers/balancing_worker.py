from __future__ import annotations

from decimal import Decimal

import structlog

from gridmind.core.types import BalancingMode
from gridmind.db.session import session_scope
from gridmind.domains.balancing.service import BalancingService
from gridmind.workers.base import Worker

logger = structlog.get_logger(__name__)


class BalancingWorker(Worker):
    """Periodic grid balancing evaluation worker."""

    name = "balancing_worker"
    poll_interval_seconds = 30.0

    def __init__(self, monitored_zones: list[dict] | None = None) -> None:
        super().__init__()
        self._zones = monitored_zones or []

    async def process_batch(self) -> int:
        actions_taken = 0
        async with session_scope() as session:
            service = BalancingService(session)
            for zone in self._zones:
                from uuid import UUID
                zone_id = UUID(zone["zone_id"])
                snapshot = await service.record_snapshot(
                    zone_id,
                    Decimal(str(zone.get("supply_mw", 1000))),
                    Decimal(str(zone.get("demand_mw", 1000))),
                    Decimal(str(zone.get("reserve_mw", 200))),
                    mode=BalancingMode.REALTIME,
                )
                if abs(snapshot.net_imbalance_mw) > Decimal("50"):
                    actions = await service.execute_balancing(
                        zone_id, available_resources=zone.get("resources", [])
                    )
                    actions_taken += len(actions)
        return actions_taken
