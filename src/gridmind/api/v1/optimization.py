from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.api.deps import get_session
from gridmind.api.schemas.optimization import OptimizationRunRequest, OptimizationRunResponse
from gridmind.domains.optimization.engine import OptimizationStage
from gridmind.domains.optimization.service import OptimizationService

router = APIRouter(prefix="/optimization", tags=["optimization"])


@router.post("/runs", response_model=OptimizationRunResponse, status_code=201)
async def start_optimization_run(
    request: OptimizationRunRequest,
    session: AsyncSession = Depends(get_session),
) -> OptimizationRunResponse:
    service = OptimizationService(session)
    stages = [
        OptimizationStage(stage_name="cost", objective="minimize_cost"),
        OptimizationStage(stage_name="renewable", objective="maximize_renewable"),
        OptimizationStage(stage_name="reserve", objective="balance_reserve"),
    ]
    input_data = {
        "demand_mw": request.demand_mw,
        "available_reserve_mw": request.available_reserve_mw,
        "reserve_margin_pct": request.reserve_margin_pct,
        "resources": request.resources,
    }
    run = await service.start_run(
        request.zone_id, request.run_type, stages, input_data,
        timeout_seconds=request.timeout_seconds,
    )
    return OptimizationRunResponse.model_validate(run)


@router.get("/runs/{run_id}", response_model=OptimizationRunResponse)
async def get_optimization_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> OptimizationRunResponse:
    from gridmind.db.models.optimization import OptimizationRun
    run = await session.get(OptimizationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Optimization run not found")
    return OptimizationRunResponse.model_validate(run)
