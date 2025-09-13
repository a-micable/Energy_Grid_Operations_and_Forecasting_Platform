from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from gridmind.core.exceptions import SchedulingConflictError


@dataclass
class ScheduleSlot:
    start: datetime
    end: datetime
    resource_id: UUID
    activity_type: str
    priority: int = 100
    metadata: dict[str, Any] | None = None


@dataclass
class ScheduleConflict:
    slot_a: ScheduleSlot
    slot_b: ScheduleSlot
    conflict_type: str
    overlap_minutes: float


class SchedulingEngine:
    """Cross-domain scheduling with conflict detection and resolution."""

    def detect_conflicts(self, slots: list[ScheduleSlot]) -> list[ScheduleConflict]:
        conflicts: list[ScheduleConflict] = []
        by_resource: dict[UUID, list[ScheduleSlot]] = {}
        for slot in slots:
            by_resource.setdefault(slot.resource_id, []).append(slot)

        for resource_id, resource_slots in by_resource.items():
            sorted_slots = sorted(resource_slots, key=lambda s: s.start)
            for i, slot_a in enumerate(sorted_slots):
                for slot_b in sorted_slots[i + 1:]:
                    if slot_a.end <= slot_b.start:
                        break
                    overlap_start = max(slot_a.start, slot_b.start)
                    overlap_end = min(slot_a.end, slot_b.end)
                    overlap_minutes = (overlap_end - overlap_start).total_seconds() / 60
                    conflict_type = "hard" if slot_a.priority == slot_b.priority else "soft"
                    conflicts.append(
                        ScheduleConflict(
                            slot_a=slot_a,
                            slot_b=slot_b,
                            conflict_type=conflict_type,
                            overlap_minutes=overlap_minutes,
                        )
                    )
        return conflicts

    def resolve_conflicts(
        self,
        slots: list[ScheduleSlot],
        conflicts: list[ScheduleConflict],
        *,
        strategy: str = "priority",
    ) -> list[ScheduleSlot]:
        resolved = list(slots)
        for conflict in conflicts:
            if strategy == "priority":
                lower = (
                    conflict.slot_a
                    if conflict.slot_a.priority > conflict.slot_b.priority
                    else conflict.slot_b
                )
                if lower in resolved:
                    resolved.remove(lower)
            elif strategy == "shift":
                to_shift = (
                    conflict.slot_b
                    if conflict.slot_a.priority <= conflict.slot_b.priority
                    else conflict.slot_a
                )
                duration = to_shift.end - to_shift.start
                idx = resolved.index(to_shift)
                resolved[idx] = ScheduleSlot(
                    start=conflict.slot_a.end,
                    end=conflict.slot_a.end + duration,
                    resource_id=to_shift.resource_id,
                    activity_type=to_shift.activity_type,
                    priority=to_shift.priority,
                )
        return resolved

    def optimize_schedule(
        self,
        slots: list[ScheduleSlot],
        *,
        max_iterations: int = 100,
    ) -> tuple[list[ScheduleSlot], list[ScheduleConflict]]:
        current = list(slots)
        for _ in range(max_iterations):
            conflicts = self.detect_conflicts(current)
            if not conflicts:
                return current, []
            hard = [c for c in conflicts if c.conflict_type == "hard"]
            if hard:
                current = self.resolve_conflicts(current, hard, strategy="priority")
            else:
                current = self.resolve_conflicts(current, conflicts, strategy="shift")
        remaining = self.detect_conflicts(current)
        return current, remaining

    def compute_utilization(
        self, slots: list[ScheduleSlot], window_start: datetime, window_end: datetime
    ) -> dict[UUID, float]:
        utilization: dict[UUID, float] = {}
        window_minutes = (window_end - window_start).total_seconds() / 60
        if window_minutes <= 0:
            return utilization
        by_resource: dict[UUID, float] = {}
        for slot in slots:
            overlap_start = max(slot.start, window_start)
            overlap_end = min(slot.end, window_end)
            if overlap_start < overlap_end:
                minutes = (overlap_end - overlap_start).total_seconds() / 60
                by_resource[slot.resource_id] = by_resource.get(slot.resource_id, 0) + minutes
        for rid, minutes in by_resource.items():
            utilization[rid] = min(1.0, minutes / window_minutes)
        return utilization
