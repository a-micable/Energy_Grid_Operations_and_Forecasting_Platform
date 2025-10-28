from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class Worker(ABC):
    """Base class for background workers."""

    name: str = "base_worker"
    poll_interval_seconds: float = 5.0

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    @abstractmethod
    async def process_batch(self) -> int:
        """Process a batch of work. Returns count processed."""
        ...

    async def run_once(self) -> int:
        try:
            count = await self.process_batch()
            if count > 0:
                logger.info("worker_batch_processed", worker=self.name, count=count)
            return count
        except Exception:
            logger.exception("worker_batch_failed", worker=self.name)
            return 0

    async def start(self) -> None:
        self._running = True
        logger.info("worker_started", worker=self.name)
        while self._running:
            await self.run_once()
            await asyncio.sleep(self.poll_interval_seconds)

    async def stop(self) -> None:
        self._running = False
        logger.info("worker_stopped", worker=self.name)
