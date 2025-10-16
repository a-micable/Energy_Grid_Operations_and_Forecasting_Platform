from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.api.deps import get_session
from gridmind.api.schemas.forecasting import (
    CreateForecastRequest,
    ForecastRunResponse,
    ReviseForecastRequest,
)
from gridmind.core.exceptions import ForecastDriftError, GridMindError
from gridmind.domains.forecasting.engine import ForecastPointData
from gridmind.domains.forecasting.service import ForecastingService
from gridmind.services.audit import AuditService

router = APIRouter(prefix="/forecasts", tags=["forecasting"])


def _handle_error(exc: GridMindError) -> HTTPException:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "NOT_FOUND":
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code == "FORECAST_DRIFT":
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.message})


@router.post("", response_model=ForecastRunResponse, status_code=status.HTTP_201_CREATED)
async def create_forecast(
    request: CreateForecastRequest,
    session: AsyncSession = Depends(get_session),
) -> ForecastRunResponse:
    service = ForecastingService(session, audit=AuditService(session))
    try:
        run = await service.create_forecast_run(
            request.zone_id,
            request.forecast_type,
            request.horizon,
            model_name=request.model_name,
            base_load_mw=request.base_load_mw,
            hours=request.hours,
        )
        return ForecastRunResponse.model_validate(run)
    except GridMindError as exc:
        raise _handle_error(exc) from exc


@router.get("/{run_id}", response_model=ForecastRunResponse)
async def get_forecast(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ForecastRunResponse:
    from gridmind.db.repositories.forecasting import ForecastRunRepository
    repo = ForecastRunRepository(session)
    try:
        run = await repo.get_by_id_or_raise(run_id)
        return ForecastRunResponse.model_validate(run)
    except GridMindError as exc:
        raise _handle_error(exc) from exc


@router.post("/{run_id}/revise", response_model=ForecastRunResponse)
async def revise_forecast(
    run_id: UUID,
    request: ReviseForecastRequest,
    session: AsyncSession = Depends(get_session),
) -> ForecastRunResponse:
    service = ForecastingService(session, audit=AuditService(session))
    points = [
        ForecastPointData(
            timestamp=p.timestamp,
            value_mw=p.value_mw,
            lower_bound_mw=p.lower_bound_mw,
            upper_bound_mw=p.upper_bound_mw,
        )
        for p in request.points
    ]
    try:
        await service.revise_forecast(
            run_id, points, reason=request.reason, revised_by=request.revised_by, force=request.force
        )
        from gridmind.db.repositories.forecasting import ForecastRunRepository
        run = await ForecastRunRepository(session).get_by_id_or_raise(run_id)
        return ForecastRunResponse.model_validate(run)
    except ForecastDriftError as exc:
        raise _handle_error(exc) from exc
