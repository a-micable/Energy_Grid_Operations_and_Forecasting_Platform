from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.api.deps import get_session
from gridmind.api.schemas.balancing import (
    BalancingSnapshotResponse,
    ExecuteBalancingRequest,
    RecordSnapshotRequest,
)
from gridmind.domains.balancing.service import BalancingService
from gridmind.services.audit import AuditService

router = APIRouter(prefix="/balancing", tags=["balancing"])


@router.post("/snapshots", response_model=BalancingSnapshotResponse, status_code=201)
async def record_snapshot(
    request: RecordSnapshotRequest,
    session: AsyncSession = Depends(get_session),
) -> BalancingSnapshotResponse:
    service = BalancingService(session, audit=AuditService(session))
    snapshot = await service.record_snapshot(
        request.zone_id,
        request.supply_mw,
        request.demand_mw,
        request.reserve_mw,
        mode=request.mode,
        frequency_hz=request.frequency_hz,
    )
    return BalancingSnapshotResponse.model_validate(snapshot)


@router.get("/zones/{zone_id}/latest", response_model=BalancingSnapshotResponse)
async def get_latest_snapshot(
    zone_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> BalancingSnapshotResponse:
    from gridmind.db.repositories.balancing import BalancingSnapshotRepository
    repo = BalancingSnapshotRepository(session)
    snapshot = await repo.get_latest(zone_id)
    if not snapshot:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No snapshot found")
    return BalancingSnapshotResponse.model_validate(snapshot)


@router.post("/execute", status_code=202)
async def execute_balancing(
    request: ExecuteBalancingRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = BalancingService(session, audit=AuditService(session))
    actions = await service.execute_balancing(
        request.zone_id, available_resources=[], mode=request.mode, actor=request.actor
    )
    return {"actions_created": len(actions)}
