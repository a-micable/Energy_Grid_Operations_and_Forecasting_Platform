from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.core.exceptions import DispatchConflictError
from gridmind.core.types import DispatchStatus
from gridmind.db.models.dispatch import DispatchInstruction, DispatchPlan
from gridmind.db.repositories.dispatch import DispatchInstructionRepository, DispatchPlanRepository
from gridmind.domains.dispatch.optimizer import DispatchOptimizer, OptimizationResult, ResourceOffer
from gridmind.services.audit import AuditService


class DispatchService:
    def __init__(
        self,
        session: AsyncSession,
        optimizer: DispatchOptimizer | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._session = session
        self._optimizer = optimizer or DispatchOptimizer()
        self._plan_repo = DispatchPlanRepository(session)
        self._instruction_repo = DispatchInstructionRepository(session)
        self._audit = audit

    async def create_dispatch_plan(
        self,
        zone_id: UUID,
        demand_mw: Decimal,
        resources: list[ResourceOffer],
        horizon_start: datetime,
        horizon_end: datetime,
        *,
        created_by: str,
    ) -> tuple[DispatchPlan, OptimizationResult]:
        plan = DispatchPlan(
            zone_id=zone_id,
            status=DispatchStatus.OPTIMIZING.value,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            created_by=created_by,
        )
        await self._plan_repo.add(plan)

        result = self._optimizer.optimize(demand_mw, resources, horizon_start, horizon_end)

        for alloc in result.allocations:
            conflicts = await self._instruction_repo.find_conflicts(
                alloc.resource_id, alloc.start, alloc.end
            )
            if conflicts:
                raise DispatchConflictError(
                    f"Dispatch conflict for resource {alloc.resource_id}",
                    details={"conflicts": [str(c.id) for c in conflicts]},
                )
            instruction = DispatchInstruction(
                plan_id=plan.id,
                resource_id=alloc.resource_id,
                scheduled_start=alloc.start,
                scheduled_end=alloc.end,
                target_output_mw=alloc.output_mw,
                marginal_cost=alloc.cost / alloc.output_mw if alloc.output_mw else None,
            )
            await self._instruction_repo.add(instruction)

        plan.status = DispatchStatus.SCHEDULED.value
        plan.total_cost = result.total_cost
        plan.total_emissions_kg = result.total_emissions_kg
        await self._session.flush()

        if self._audit:
            await self._audit.record(
                "dispatch_plan", plan.id, "created", created_by,
                after_state={
                    "total_cost": str(result.total_cost),
                    "allocations": len(result.allocations),
                },
            )
        return plan, result
