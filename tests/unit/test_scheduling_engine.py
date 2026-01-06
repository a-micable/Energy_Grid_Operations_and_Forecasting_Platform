from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from gridmind.domains.scheduling.engine import ScheduleSlot, SchedulingEngine


class TestSchedulingEngine:
    def setup_method(self) -> None:
        self.engine = SchedulingEngine()
        self.base = datetime(2025, 8, 1, 8, 0, tzinfo=timezone.utc)
        self.rid = uuid4()

    def test_detect_conflicts_overlapping_slots(self) -> None:
        slots = [
            ScheduleSlot(self.base, self.base + timedelta(hours=4), self.rid, "outage"),
            ScheduleSlot(self.base + timedelta(hours=2), self.base + timedelta(hours=6), self.rid, "maintenance"),
        ]
        conflicts = self.engine.detect_conflicts(slots)
        assert len(conflicts) == 1
        assert conflicts[0].overlap_minutes == 120

    def test_no_conflicts_for_non_overlapping(self) -> None:
        slots = [
            ScheduleSlot(self.base, self.base + timedelta(hours=2), self.rid, "outage"),
            ScheduleSlot(self.base + timedelta(hours=2), self.base + timedelta(hours=4), self.rid, "maintenance"),
        ]
        assert len(self.engine.detect_conflicts(slots)) == 0

    def test_optimize_schedule_resolves_conflicts(self) -> None:
        slots = [
            ScheduleSlot(self.base, self.base + timedelta(hours=4), self.rid, "outage", priority=10),
            ScheduleSlot(self.base + timedelta(hours=1), self.base + timedelta(hours=5), self.rid, "maintenance", priority=50),
        ]
        optimized, remaining = self.engine.optimize_schedule(slots)
        assert len(remaining) == 0 or len(optimized) < len(slots)

    def test_utilization_calculation(self) -> None:
        slots = [
            ScheduleSlot(self.base, self.base + timedelta(hours=2), self.rid, "dispatch"),
        ]
        window_end = self.base + timedelta(hours=4)
        util = self.engine.compute_utilization(slots, self.base, window_end)
        assert util[self.rid] == 0.5
