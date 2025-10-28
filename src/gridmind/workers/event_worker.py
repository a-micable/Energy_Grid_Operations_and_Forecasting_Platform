from __future__ import annotations

import structlog

from gridmind.db.session import session_scope
from gridmind.domains.events.service import EventService
from gridmind.workers.base import Worker

logger = structlog.get_logger(__name__)


class EventWorker(Worker):
    """Process pending events from the event queue."""

    name = "event_worker"
    poll_interval_seconds = 2.0

    async def process_batch(self) -> int:
        async with session_scope() as session:
            service = EventService(session)
            return await service.process_pending(limit=50)
