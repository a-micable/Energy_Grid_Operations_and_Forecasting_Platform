from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.api.deps import get_session
from gridmind.api.schemas.outage import (
    AddDependencyRequest,
    CreateOutageRequest,
    OutageResponse,
    TransitionOutageRequest,
)
from gridmind.core.exceptions import GridMindError
from gridmind.domains.outage.service import OutageService
from gridmind.services.audit import AuditService

router = APIRouter(prefix="/outages", tags=["outages"])


@router.post("", response_model=OutageResponse, status_code=201)
async def create_outage(
    request: CreateOutageRequest,
    session: AsyncSession = Depends(get_session),
) -> OutageResponse:
    service = OutageService(session, audit=AuditService(session))
    try:
        outage = await service.create_outage(
            request.zone_id,
            request.title,
            request.outage_type,
            request.planned_start,
            request.planned_end,
            request.impact_mw,
            request.resource_ids,
            created_by=request.created_by,
            description=request.description,
        )
        return OutageResponse.model_validate(outage)
    except GridMindError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/{outage_id}/transition", response_model=OutageResponse)
async def transition_outage(
    outage_id: UUID,
    request: TransitionOutageRequest,
    session: AsyncSession = Depends(get_session),
) -> OutageResponse:
    service = OutageService(session, audit=AuditService(session))
    try:
        outage = await service.transition_status(outage_id, request.target_status, actor=request.actor)
        return OutageResponse.model_validate(outage)
    except GridMindError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/{outage_id}/dependencies", status_code=201)
async def add_dependency(
    outage_id: UUID,
    request: AddDependencyRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = OutageService(session)
    try:
        dep = await service.add_dependency(
            outage_id, request.depends_on_outage_id, request.dependency_type, is_hard=request.is_hard
        )
        return {"id": str(dep.id), "dependency_type": dep.dependency_type}
    except GridMindError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
