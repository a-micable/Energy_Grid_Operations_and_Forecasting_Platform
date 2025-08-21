from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID


class HistoricalReconstructor:
    """Reconstruct entity state at any point in time from audit trail."""

    def __init__(self, entries: list[dict]) -> None:
        self._entries = sorted(entries, key=lambda e: e["occurred_at"])

    def reconstruct_at(self, at: datetime) -> dict[str, Any] | None:
        state: dict[str, Any] | None = None
        for entry in self._entries:
            if entry["occurred_at"] > at:
                break
            if entry.get("after_state"):
                state = dict(entry["after_state"])
            elif entry.get("action") == "deleted":
                state = None
        return state

    def build_timeline(
        self, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        timeline: list[dict[str, Any]] = []
        for entry in self._entries:
            if start <= entry["occurred_at"] <= end:
                timeline.append({
                    "occurred_at": entry["occurred_at"],
                    "action": entry["action"],
                    "actor": entry["actor"],
                    "entity_type": entry.get("entity_type"),
                    "entity_id": entry.get("entity_id"),
                    "changes": self._diff_states(
                        entry.get("before_state"), entry.get("after_state")
                    ),
                })
        return timeline

    def _diff_states(
        self, before: dict | None, after: dict | None
    ) -> dict[str, Any]:
        if before is None and after is None:
            return {}
        if before is None:
            return {"added": after}
        if after is None:
            return {"removed": before}
        changes: dict[str, Any] = {}
        all_keys = set(before.keys()) | set(after.keys())
        for key in all_keys:
            if before.get(key) != after.get(key):
                changes[key] = {"from": before.get(key), "to": after.get(key)}
        return changes

    def verify_integrity(self) -> list[str]:
        issues: list[str] = []
        prev_state: dict | None = None
        for i, entry in enumerate(self._entries):
            if entry.get("before_state") and prev_state:
                if entry["before_state"] != prev_state:
                    issues.append(
                        f"State mismatch at entry {i}: expected {prev_state}, "
                        f"got {entry['before_state']}"
                    )
            if entry.get("after_state"):
                prev_state = entry["after_state"]
        return issues
