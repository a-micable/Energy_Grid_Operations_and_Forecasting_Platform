from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from gridmind.core.exceptions import DependencyGraphError, SchedulingConflictError
from gridmind.core.types import OutageStatus, OutageType


@dataclass
class OutageConflict:
    outage_id: UUID
    conflicting_outage_id: UUID
    conflict_type: str
    resource_id: UUID | None = None
    overlap_start: datetime | None = None
    overlap_end: datetime | None = None


@dataclass
class DependencyNode:
    outage_id: UUID
    depends_on: list[UUID] = field(default_factory=list)
    dependents: list[UUID] = field(default_factory=list)


class OutagePlanner:
    """Outage scheduling with conflict detection and dependency management."""

    VALID_TRANSITIONS: dict[OutageStatus, set[OutageStatus]] = {
        OutageStatus.DRAFT: {OutageStatus.SCHEDULED, OutageStatus.CANCELLED},
        OutageStatus.SCHEDULED: {OutageStatus.APPROVED, OutageStatus.CANCELLED},
        OutageStatus.APPROVED: {OutageStatus.IN_PROGRESS, OutageStatus.CANCELLED},
        OutageStatus.IN_PROGRESS: {OutageStatus.COMPLETED},
        OutageStatus.COMPLETED: set(),
        OutageStatus.CANCELLED: set(),
    }

    def validate_transition(self, current: OutageStatus, target: OutageStatus) -> bool:
        return target in self.VALID_TRANSITIONS.get(current, set())

    def detect_time_overlap(
        self,
        start_a: datetime,
        end_a: datetime,
        start_b: datetime,
        end_b: datetime,
    ) -> tuple[datetime, datetime] | None:
        overlap_start = max(start_a, start_b)
        overlap_end = min(end_a, end_b)
        if overlap_start < overlap_end:
            return overlap_start, overlap_end
        return None

    def find_conflicts(
        self,
        outage_id: UUID,
        planned_start: datetime,
        planned_end: datetime,
        resource_ids: list[UUID],
        existing_outages: list[dict],
    ) -> list[OutageConflict]:
        conflicts: list[OutageConflict] = []
        for existing in existing_outages:
            if existing["id"] == outage_id:
                continue
            overlap = self.detect_time_overlap(
                planned_start, planned_end,
                existing["planned_start"], existing["planned_end"],
            )
            if not overlap:
                continue
            shared_resources = set(resource_ids) & set(existing.get("resource_ids", []))
            if shared_resources:
                for rid in shared_resources:
                    conflicts.append(
                        OutageConflict(
                            outage_id=outage_id,
                            conflicting_outage_id=existing["id"],
                            conflict_type="resource_overlap",
                            resource_id=rid,
                            overlap_start=overlap[0],
                            overlap_end=overlap[1],
                        )
                    )
            elif existing.get("zone_id") == existing.get("zone_id"):
                conflicts.append(
                    OutageConflict(
                        outage_id=outage_id,
                        conflicting_outage_id=existing["id"],
                        conflict_type="temporal_overlap",
                        overlap_start=overlap[0],
                        overlap_end=overlap[1],
                    )
                )
        return conflicts

    def build_dependency_graph(
        self, dependencies: list[tuple[UUID, UUID]]
    ) -> dict[UUID, DependencyNode]:
        graph: dict[UUID, DependencyNode] = {}
        for outage_id, depends_on_id in dependencies:
            if outage_id not in graph:
                graph[outage_id] = DependencyNode(outage_id=outage_id)
            if depends_on_id not in graph:
                graph[depends_on_id] = DependencyNode(outage_id=depends_on_id)
            graph[outage_id].depends_on.append(depends_on_id)
            graph[depends_on_id].dependents.append(outage_id)
        return graph

    def topological_sort(self, graph: dict[UUID, DependencyNode]) -> list[UUID]:
        in_degree: dict[UUID, int] = {nid: len(node.depends_on) for nid, node in graph.items()}
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result: list[UUID] = []
        while queue:
            current = queue.pop(0)
            result.append(current)
            node = graph.get(current)
            if not node:
                continue
            for dependent in node.dependents:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        if len(result) != len(graph):
            raise DependencyGraphError("Circular dependency detected in outage graph")
        return result

    def optimize_schedule(
        self,
        outages: list[dict],
        dependencies: list[tuple[UUID, UUID]],
        *,
        buffer_hours: int = 4,
    ) -> list[dict]:
        graph = self.build_dependency_graph(dependencies)
        order = self.topological_sort(graph)
        scheduled: dict[UUID, dict] = {}
        buffer = timedelta(hours=buffer_hours)
        for oid in order:
            outage = next(o for o in outages if o["id"] == oid)
            earliest = outage["planned_start"]
            node = graph.get(oid)
            if node:
                for dep_id in node.depends_on:
                    if dep_id in scheduled:
                        dep_end = scheduled[dep_id]["planned_end"] + buffer
                        if dep_end > earliest:
                            duration = outage["planned_end"] - outage["planned_start"]
                            earliest = dep_end
                            outage = {**outage, "planned_start": earliest, "planned_end": earliest + duration}
            scheduled[oid] = outage
        return [scheduled[oid] for oid in order if oid in scheduled]
