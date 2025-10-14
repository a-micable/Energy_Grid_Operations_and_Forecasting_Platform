from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.api.deps import get_session
from gridmind.api.schemas.dispatch import CreateDispatchPlanRequest, DispatchPlanResponse
from gridmind.core.exceptions import GridMindError
from gridmind.domains.dispatch.optimizer import ResourceOffer
from gridmind.domains.dispatch.service import DispatchService
from gridmind.services.audit import AuditService

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


@router.post("/plans", response_model=DispatchPlanResponse, status_code=201)
async def create_dispatch_plan(
    request: CreateDispatchPlanRequest,
    session: AsyncSession = Depends(get_session),
) -> DispatchPlanResponse:
    service = DispatchService(session, audit=AuditService(session))
    resources = [
        ResourceOffer(
            resource_id=r.resource_id,
            resource_type=r.resource_type,
            min_output_mw=r.min_output_mw,
            max_output_mw=r.max_output_mw,
            marginal_cost=r.marginal_cost,
            emission_rate=r.emission_rate,
            dispatch_priority=r.dispatch_priority,
            ramp_rate_mw_per_min=__import__("decimal").Decimal("1"),
        )
        for r in request.resources
    ]
    try:
        plan, _ = await service.create_dispatch_plan(
            request.zone_id,
            request.demand_mw,
            resources,
            request.horizon_start,
            request.horizon_end,
            created_by=request.created_by,
        )
        return DispatchPlanResponse.model_validate(plan)
    except GridMindError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get("/plans/{plan_id}", response_model=DispatchPlanResponse)
async def get_dispatch_plan(
    plan_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> DispatchPlanResponse:
    from gridmind.db.repositories.dispatch import DispatchPlanRepository
    repo = DispatchPlanRepository(session)
    try:
        plan = await repo.get_by_id_or_raise(plan_id)
        return DispatchPlanResponse.model_validate(plan)
    except GridMindError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
