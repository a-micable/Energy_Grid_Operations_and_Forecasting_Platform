from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.core.exceptions import ConflictError, SchedulingConflictError, StateTransitionError
from gridmind.core.types import OutageStatus, OutageType
from gridmind.db.models.outage import OutageDependency, OutagePlan, OutageResource
from gridmind.db.repositories.outage import (
    OutageDependencyRepository,
    OutagePlanRepository,
    OutageResourceRepository,
)
from gridmind.domains.outage.planner import OutagePlanner
from gridmind.services.audit import AuditService


class OutageService:
    def __init__(
        self,
        session: AsyncSession,
        planner: OutagePlanner | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._session = session
        self._planner = planner or OutagePlanner()
        self._plan_repo = OutagePlanRepository(session)
        self._resource_repo = OutageResourceRepository(session)
        self._dep_repo = OutageDependencyRepository(session)
        self._audit = audit

    async def create_outage(
        self,
        zone_id: UUID,
        title: str,
        outage_type: OutageType,
        planned_start: datetime,
        planned_end: datetime,
        impact_mw: float,
        resource_ids: list[UUID],
        *,
        created_by: str,
        description: str | None = None,
    ) -> OutagePlan:
        outage = OutagePlan(
            zone_id=zone_id,
            title=title,
            outage_type=outage_type.value,
            planned_start=planned_start,
            planned_end=planned_end,
            impact_mw=impact_mw,
            description=description,
            created_by=created_by,
        )
        await self._plan_repo.add(outage)

        for rid in resource_ids:
            await self._resource_repo.add(
                OutageResource(outage_id=outage.id, resource_id=rid)
            )

        overlapping = await self._plan_repo.find_overlapping(
            zone_id, planned_start, planned_end, exclude_id=outage.id
        )
        if overlapping:
            for o in overlapping:
                conflicts = await self._resource_repo.find_conflicts(
                    resource_ids[0] if resource_ids else UUID(int=0),
                    planned_start, planned_end,
                )
                if conflicts:
                    raise SchedulingConflictError(
                        f"Outage conflicts with existing outage {o.id}"
                    )

        if self._audit:
            await self._audit.record(
                "outage", outage.id, "created", created_by,
                after_state={"status": "draft", "title": title},
            )
        return outage

    async def transition_status(
        self, outage_id: UUID, target: OutageStatus, *, actor: str
    ) -> OutagePlan:
        outage = await self._plan_repo.get_by_id_or_raise(outage_id)
        current = OutageStatus(outage.status)
        if not self._planner.validate_transition(current, target):
            raise StateTransitionError("outage", outage_id, current.value, target.value)
        outage.status = target.value
        if target == OutageStatus.IN_PROGRESS:
            outage.actual_start = datetime.now(timezone.utc)
        elif target == OutageStatus.COMPLETED:
            outage.actual_end = datetime.now(timezone.utc)
        await self._session.flush()
        if self._audit:
            await self._audit.record(
                "outage", outage_id, "status_change", actor,
                before_state={"status": current.value},
                after_state={"status": target.value},
            )
        return outage

    async def add_dependency(
        self, outage_id: UUID, depends_on_id: UUID, dependency_type: str, *, is_hard: bool = True
    ) -> OutageDependency:
        if await self._dep_repo.has_cycle(outage_id, depends_on_id):
            from gridmind.core.exceptions import DependencyGraphError
            raise DependencyGraphError(
                f"Adding dependency {depends_on_id} -> {outage_id} would create cycle"
            )
        dep = OutageDependency(
            outage_id=outage_id,
            depends_on_outage_id=depends_on_id,
            dependency_type=dependency_type,
            is_hard=is_hard,
        )
        await self._dep_repo.add(dep)
        return dep
