from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from gridmind.core.exceptions import DependencyGraphError
from gridmind.core.types import OutageStatus
from gridmind.domains.outage.planner import OutagePlanner


class TestOutagePlanner:
    def setup_method(self) -> None:
        self.planner = OutagePlanner()
        self.base_time = datetime(2025, 7, 1, 8, 0, tzinfo=timezone.utc)

    def test_valid_state_transitions(self) -> None:
        assert self.planner.validate_transition(OutageStatus.DRAFT, OutageStatus.SCHEDULED)
        assert not self.planner.validate_transition(OutageStatus.COMPLETED, OutageStatus.DRAFT)

    def test_time_overlap_detection(self) -> None:
        overlap = self.planner.detect_time_overlap(
            self.base_time, self.base_time + timedelta(hours=4),
            self.base_time + timedelta(hours=2), self.base_time + timedelta(hours=6),
        )
        assert overlap is not None

    def test_no_overlap_for_adjacent_windows(self) -> None:
        overlap = self.planner.detect_time_overlap(
            self.base_time, self.base_time + timedelta(hours=4),
            self.base_time + timedelta(hours=4), self.base_time + timedelta(hours=8),
        )
        assert overlap is None

    def test_conflict_detection_for_shared_resource(self) -> None:
        rid = uuid4()
        oid1 = uuid4()
        oid2 = uuid4()
        existing = [{
            "id": oid2,
            "planned_start": self.base_time + timedelta(hours=1),
            "planned_end": self.base_time + timedelta(hours=5),
            "resource_ids": [rid],
            "zone_id": uuid4(),
        }]
        conflicts = self.planner.find_conflicts(
            oid1,
            self.base_time,
            self.base_time + timedelta(hours=3),
            [rid],
            existing,
        )
        assert len(conflicts) > 0
        assert conflicts[0].conflict_type == "resource_overlap"

    def test_circular_dependency_detection(self) -> None:
        a, b, c = uuid4(), uuid4(), uuid4()
        with pytest.raises(DependencyGraphError):
            self.planner.topological_sort({
                a: __import__("gridmind.domains.outage.planner", fromlist=["DependencyNode"]).DependencyNode(
                    outage_id=a, depends_on=[c]
                ),
                b: __import__("gridmind.domains.outage.planner", fromlist=["DependencyNode"]).DependencyNode(
                    outage_id=b, depends_on=[a]
                ),
                c: __import__("gridmind.domains.outage.planner", fromlist=["DependencyNode"]).DependencyNode(
                    outage_id=c, depends_on=[b]
                ),
            })

    def test_topological_sort_valid_graph(self) -> None:
        from gridmind.domains.outage.planner import DependencyNode
        a, b, c = uuid4(), uuid4(), uuid4()
        graph = {
            a: DependencyNode(outage_id=a, depends_on=[]),
            b: DependencyNode(outage_id=b, depends_on=[a]),
            c: DependencyNode(outage_id=c, depends_on=[b]),
        }
        order = self.planner.topological_sort(graph)
        assert order.index(a) < order.index(b) < order.index(c)
