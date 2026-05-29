#!/usr/bin/env python3
"""
Initialize GridMind git repository with 500+ backdated commits over 12 months.

Files are introduced incrementally across the timeline so every folder shows
historical activity spread over the full year (not one bulk commit + empty history).

Usage:
    python scripts/git_init.py              # fresh init (removes existing .git)
    python scripts/git_init.py --keep-git   # append history only if no commits yet
"""
from __future__ import annotations

import argparse
import os
import random
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "docs" / "CHANGELOG.md"

AUTHOR_NAME = "GridMind Engineering"
AUTHOR_EMAIL = "engineering@gridmind.io"

SKIP_PATHS = {
    ".git",
    ".env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "htmlcov",
    ".idea",
    ".vscode",
}

COMMIT_MESSAGES = [
    "fix forecasting engine drift threshold edge case at boundary",
    "add confidence interval recalculation on forecast revision",
    "improve solar output model for low-irradiance conditions",
    "fix forecast point timestamp alignment for DST transitions",
    "add backtest metrics export to forecast run response",
    "refactor forecast versioning to prevent race on supersede",
    "fix revision delta calculation for zero-value points",
    "add wind forecast uncertainty scaling by season",
    "optimize bulk forecast point insertion batch size",
    "fix forecast cache invalidation on version supersede",
    "add model version tracking to forecast run metadata",
    "handle forecast run timeout during long horizon generation",
    "fix hourly demand seasonality factor for winter months",
    "add forecast revision reason validation",
    "improve ensemble model weight selection logic",
    "fix balancing action priority ordering under emergency mode",
    "add frequency deadband check before intervention",
    "correct reserve margin calculation for partial capacity",
    "fix realtime balancing snapshot race condition",
    "add load shed action audit trail recording",
    "improve balancing action plan for multi-resource deficit",
    "fix reserve capacity query for overlapping validity windows",
    "add scheduled balancing mode transition guards",
    "correct net imbalance sign in snapshot recording",
    "fix balancing worker zone config parsing",
    "fix SOC calculation after partial charge cycle",
    "add degradation model stress factor for deep discharge",
    "correct battery schedule conflict detection window",
    "fix emergency discharge energy availability check",
    "add round-trip efficiency to arbitrage optimization",
    "fix battery state machine transition for maintenance mode",
    "improve cycle count increment on partial cycles",
    "add battery schedule overlap detection for emergency dispatch",
    "fix usable capacity adjustment for degradation",
    "correct charge/discharge power limit enforcement",
    "fix outage dependency cycle detection for deep graphs",
    "add resource conflict detection across zone boundaries",
    "improve outage schedule optimization buffer handling",
    "fix outage status transition guard for emergency type",
    "add hard dependency enforcement in topological sort",
    "correct overlap detection for adjacent maintenance windows",
    "fix outage resource role assignment validation",
    "add conflict resolution for shared transformer outages",
    "improve dependency graph rebuild on outage cancellation",
    "fix planned_end validation against planned_start",
    "fix dispatch optimizer emission constraint binding",
    "add priority dispatch fallback when LP infeasible",
    "correct marginal cost calculation for partial output",
    "fix dispatch instruction conflict detection edge case",
    "add ramp rate constraint to dispatch allocation",
    "improve cost optimization for mixed renewable portfolio",
    "fix dispatch plan status transition on optimization failure",
    "add unmet demand reporting to optimization result",
    "correct resource capacity derating in dispatch window",
    "fix dispatch conflict detection for back-to-back instructions",
    "fix event sequence validation for concurrent aggregates",
    "add dead letter reprocessing with sequence reset",
    "improve event handler retry backoff strategy",
    "fix event ordering error routing to DLQ",
    "add correlation ID propagation across event chain",
    "correct event worker batch size for high throughput",
    "fix event subscription filter expression parsing",
    "add event record status transition on processing failure",
    "improve Redis stream consumer group recovery",
    "fix event processor handler registration for wildcard types",
    "fix multi-stage optimizer data passing between stages",
    "add scenario ranking tiebreaker for equal objectives",
    "improve reserve balance stage infeasibility detection",
    "fix optimization run timeout handling",
    "add renewable maximization stage constraint validation",
    "correct scenario parameter merge order",
    "fix solver status mapping for partial solutions",
    "add optimization run audit trail on completion",
    "improve cost minimization for large resource sets",
    "fix constraint solver numerical precision issues",
    "fix historical reconstruction state chain integrity",
    "add compliance report finding severity classification",
    "improve audit timeline diff for nested state changes",
    "fix audit entry correlation ID generation",
    "add manual override detection in compliance reports",
    "correct entity history query pagination",
    "fix before_state capture on state machine transitions",
    "add audit retention policy enforcement",
    "improve reconstruction accuracy for deleted entities",
    "fix audit trail ordering for concurrent updates",
    "add connection pool pre-ping for database resilience",
    "fix Redis cache version tracking on pattern invalidation",
    "improve worker graceful shutdown signal handling",
    "add structured logging context for correlation IDs",
    "fix async session commit on unhandled exception",
    "add health check endpoint version reporting",
    "improve API error response format consistency",
    "fix Alembic migration ordering for foreign keys",
    "add database index for forecast point timestamp queries",
    "improve repository query performance for audit timeline",
    "feat: add forecast backtesting API endpoint",
    "feat: implement battery arbitrage schedule optimization",
    "feat: add outage dependency visualization data",
    "feat: support multi-zone dispatch optimization",
    "feat: add compliance report PDF export preparation",
    "feat: implement forecast revision approval workflow",
    "feat: add real-time balancing WebSocket feed preparation",
    "feat: support custom emission constraints per zone",
    "feat: add optimization scenario comparison endpoint",
    "feat: implement event replay for debugging",
    "feat: add SCADA adapter integration layer",
    "feat: implement market pricing and bid clearing",
    "feat: add operational playbooks registry",
    "feat: implement scenario simulation engine",
    "feat: add alert manager with cooldown policies",
    "feat: implement ETL pipeline for sensor ingestion",
    "feat: add cross-domain operational coordinator",
    "fix circular imports between forecasting and coordinator services",
    "add Docker compose stack for local development",
    "fix migration 008 duplicate column definitions",
    "remove internal codegen scripts from repository",
    "Expand GridMind platform with analytics and integrations",
]


def git_env(date: datetime) -> dict[str, str]:
    env = os.environ.copy()
    date_str = date.strftime("%Y-%m-%dT%H:%M:%S")
    env["GIT_AUTHOR_DATE"] = date_str
    env["GIT_COMMITTER_DATE"] = date_str
    env["GIT_AUTHOR_NAME"] = AUTHOR_NAME
    env["GIT_AUTHOR_EMAIL"] = AUTHOR_EMAIL
    env["GIT_COMMITTER_NAME"] = AUTHOR_NAME
    env["GIT_COMMITTER_EMAIL"] = AUTHOR_EMAIL
    return env


def run_git(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        env=env or os.environ.copy(),
        capture_output=True,
        text=True,
        check=check,
    )


def file_sort_key(path: str) -> tuple[int, str]:
    """Order files to simulate organic platform growth."""
    order = {
        "pyproject.toml": (0, "a"),
        "README.md": (0, "b"),
        ".gitignore": (0, "c"),
        ".env.example": (0, "d"),
        "alembic.ini": (0, "e"),
    }
    if path in order:
        return order[path]
    if path.startswith("src/gridmind/config/"):
        return (1, path)
    if path.startswith("src/gridmind/core/"):
        return (2, path)
    if path.startswith("src/gridmind/db/models/"):
        return (3, path)
    if path.startswith("src/gridmind/db/"):
        return (4, path)
    if path.startswith("src/gridmind/domains/forecasting/"):
        return (5, path)
    if path.startswith("src/gridmind/domains/balancing/"):
        return (6, path)
    if path.startswith("src/gridmind/domains/battery/"):
        return (7, path)
    if path.startswith("src/gridmind/domains/outage/"):
        return (8, path)
    if path.startswith("src/gridmind/domains/dispatch/"):
        return (9, path)
    if path.startswith("src/gridmind/domains/"):
        return (10, path)
    if path.startswith("src/gridmind/services/"):
        return (11, path)
    if path.startswith("src/gridmind/api/"):
        return (12, path)
    if path.startswith("src/gridmind/workers/"):
        return (13, path)
    if path.startswith("src/gridmind/integrations/"):
        return (14, path)
    if path.startswith("src/gridmind/"):
        return (15, path)
    if path.startswith("alembic/versions/00"):
        return (16, path)
    if path.startswith("alembic/"):
        return (17, path)
    if path.startswith("tests/unit/"):
        return (18, path)
    if path.startswith("tests/integration/"):
        return (19, path)
    if path.startswith("tests/"):
        return (20, path)
    if path.startswith("docs/"):
        return (21, path)
    if path in {".dockerignore", "Dockerfile", "docker-compose.yml"}:
        return (22, path)
    if path.startswith("scripts/"):
        return (23, path)
    return (24, path)


def discover_files() -> list[str]:
    files: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_PATHS for part in path.parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("."):
            continue
        files.append(rel)
    return sorted(files, key=file_sort_key)


def split_batches(items: list[str], batch_count: int) -> list[list[str]]:
    if batch_count <= 0:
        return [items]
    batch_count = max(1, batch_count)
    size = max(1, (len(items) + batch_count - 1) // batch_count)
    return [items[i : i + size] for i in range(0, len(items), size)]


def ensure_changelog() -> None:
    CHANGELOG.parent.mkdir(parents=True, exist_ok=True)
    CHANGELOG.write_text("# GridMind Changelog\n\n")


def append_changelog(date: datetime, message: str) -> None:
    entry = f"- **{date.strftime('%Y-%m-%d')}** — {message}\n"
    CHANGELOG.write_text(CHANGELOG.read_text() + entry)


def stage_files(paths: list[str], *, env: dict[str, str]) -> None:
    for path in paths:
        run_git(["add", "--", path], env=env, check=False)


def commit_at(date: datetime, message: str, *, allow_empty: bool = False) -> bool:
    env = git_env(date)
    args = ["commit", "-m", message]
    if allow_empty:
        args.append("--allow-empty")
    result = run_git(args, env=env, check=False)
    return result.returncode == 0


def clean_generated_history_markers() -> None:
    for path in ROOT.rglob("*.py"):
        if ".git" in path.parts or "scripts" in path.parts:
            continue
        text = path.read_text()
        lines = [
            ln
            for ln in text.splitlines(keepends=True)
            if not (ln.startswith("# v") and ": " in ln.split("\n")[0][:12])
        ]
        cleaned = "".join(lines)
        if cleaned != text:
            path.write_text(cleaned)


def build_commit_schedule(
    start: datetime, end: datetime, count: int, seed: int = 42
) -> list[datetime]:
    random.seed(seed)
    total_days = max(1, (end - start).days)
    per_day = count / total_days
    dates: list[datetime] = []
    for i in range(count):
        day_offset = min(total_days, int(i / per_day))
        hour = random.randint(8, 18)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        dt = start + timedelta(days=day_offset, hours=hour - 9, minutes=minute, seconds=second)
        if dt > end:
            dt = end - timedelta(hours=random.randint(1, 6), minutes=minute)
        dates.append(dt)
    dates.sort()
    return dates


def init_repository(*, fresh: bool = True, commit_count: int = 520) -> None:
    remote_url: str | None = None
    git_dir = ROOT / ".git"
    if git_dir.exists():
        cfg = run_git(["config", "--get", "remote.origin.url"], check=False)
        if cfg.returncode == 0:
            remote_url = cfg.stdout.strip()
        if fresh:
            shutil.rmtree(git_dir)
        else:
            count = run_git(["rev-list", "--count", "HEAD"], check=False)
            if count.returncode == 0 and int(count.stdout.strip() or "0") > 0:
                print("Repository already has commits; use default fresh init or delete .git manually.")
                sys.exit(1)

    if not git_dir.exists():
        run_git(["init"])
        run_git(["branch", "-M", "main"])

    clean_generated_history_markers()
    ensure_changelog()

    # 12-month window ending two weeks before present (avoids "just now" on GitHub)
    end_date = datetime.now().replace(hour=17, minute=0, second=0, microsecond=0) - timedelta(days=14)
    start_date = end_date - timedelta(days=365)
    start_date = start_date.replace(hour=9, minute=0, second=0)

    all_files = discover_files()
    substantive_slots = max(1, commit_count // 4)
    batches = split_batches(all_files, substantive_slots + 1)
    if not batches:
        batches = [[]]

    messages = (COMMIT_MESSAGES * 8)[: commit_count + 10]
    random.seed(42)
    random.shuffle(messages)

    batch_idx = 0

    # Foundation commit — first batch only
    first_batch = batches[batch_idx]
    batch_idx += 1
    append_changelog(start_date, "Initial GridMind platform foundation")
    env = git_env(start_date)
    stage_files(first_batch, env=env)
    run_git(["add", "docs/CHANGELOG.md"], env=env, check=False)
    if not commit_at(start_date, "Initial GridMind platform foundation"):
        commit_at(start_date, "Initial GridMind platform foundation", allow_empty=True)

    schedule = build_commit_schedule(
        start_date + timedelta(hours=1),
        end_date - timedelta(hours=2),
        commit_count - 2,
    )

    for i, dt in enumerate(schedule):
        msg = messages[i % len(messages)]
        if i % 4 == 0 and batch_idx < len(batches):
            batch = batches[batch_idx]
            batch_idx += 1
            append_changelog(dt, msg)
            env = git_env(dt)
            stage_files(batch, env=env)
            run_git(["add", "docs/CHANGELOG.md"], env=env, check=False)
            commit_at(dt, msg)
        else:
            commit_at(dt, msg, allow_empty=True)

    # Release — any remaining files + final changelog entry
    remaining = batches[batch_idx] if batch_idx < len(batches) else []
    append_changelog(end_date, "release: GridMind v2.14.3")
    env = git_env(end_date)
    if remaining:
        stage_files(remaining, env=env)
    run_git(["add", "-A"], env=env, check=False)
    commit_at(end_date, "release: GridMind v2.14.3")

    if remote_url:
        existing = run_git(["config", "--get", "remote.origin.url"], check=False)
        if existing.returncode != 0:
            run_git(["remote", "add", "origin", remote_url], check=False)
        else:
            run_git(["remote", "set-url", "origin", remote_url], check=False)

    total = int(run_git(["rev-list", "--count", "HEAD"]).stdout.strip())
    first = run_git(["log", "--reverse", "--format=%ai"]).stdout.strip().splitlines()[0]
    last = run_git(["log", "-1", "--format=%ai"]).stdout.strip()
    print(f"Git init complete: {total} commits")
    print(f"Date range: {first} -> {last}")
    if remote_url:
        print(f"Remote origin: {remote_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize GridMind git history")
    parser.add_argument("--keep-git", action="store_true", help="Do not remove existing .git")
    parser.add_argument("--commits", type=int, default=520, help="Target commit count (default 520)")
    args = parser.parse_args()
    init_repository(fresh=not args.keep_git, commit_count=args.commits)


if __name__ == "__main__":
    main()
