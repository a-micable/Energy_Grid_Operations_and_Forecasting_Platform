from __future__ import annotations

import argparse
import asyncio
import sys

import structlog

logger = structlog.get_logger(__name__)


async def cmd_seed(args: argparse.Namespace) -> None:
    from gridmind.db.seed import seed_development_data
    from gridmind.db.session import session_scope
    async with session_scope() as session:
        result = await seed_development_data(session)
        logger.info("seed_complete", **result)


async def cmd_migrate(args: argparse.Namespace) -> None:
    import subprocess
    subprocess.run(["alembic", "upgrade", "head"], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(prog="gridmind", description="GridMind CLI")
    sub = parser.add_subparsers(dest="command")

    seed_parser = sub.add_parser("seed", help="Seed development data")
    seed_parser.set_defaults(func=cmd_seed)

    migrate_parser = sub.add_parser("migrate", help="Run database migrations")
    migrate_parser.set_defaults(func=cmd_migrate)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
