from __future__ import annotations

import asyncio
import signal

import structlog

from gridmind.workers.balancing_worker import BalancingWorker
from gridmind.workers.event_worker import EventWorker
from gridmind.workers.forecast_worker import ForecastWorker

logger = structlog.get_logger(__name__)


async def main() -> None:
    workers = [
        EventWorker(),
        ForecastWorker(),
        BalancingWorker(),
    ]
    tasks = [asyncio.create_task(w.start()) for w in workers]

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(workers, tasks)))

    logger.info("worker_runner_started", workers=[w.name for w in workers])
    await asyncio.gather(*tasks)


async def shutdown(workers: list, tasks: list) -> None:
    logger.info("worker_runner_shutting_down")
    for w in workers:
        await w.stop()
    for t in tasks:
        t.cancel()


if __name__ == "__main__":
    asyncio.run(main())
