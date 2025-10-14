from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.api.deps import get_session
from gridmind.api.schemas.battery import (
    BatteryAssetResponse,
    RecordCycleRequest,
    ScheduleBatteryRequest,
    TransitionBatteryStateRequest,
)
from gridmind.core.exceptions import GridMindError
from gridmind.domains.battery.service import BatteryService
from gridmind.services.audit import AuditService

router = APIRouter(prefix="/batteries", tags=["battery"])


@router.post("/{battery_id}/schedule", status_code=201)
async def schedule_battery(
    battery_id: UUID,
    request: ScheduleBatteryRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = BatteryService(session, audit=AuditService(session))
    try:
        schedule = await service.schedule_dispatch(
            battery_id, request.action, request.power_mw,
            request.duration_minutes, request.scheduled_at,
            is_emergency=request.is_emergency,
        )
        return {"id": str(schedule.id), "status": schedule.status}
    except GridMindError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/{battery_id}/transition")
async def transition_battery_state(
    battery_id: UUID,
    request: TransitionBatteryStateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = BatteryService(session, audit=AuditService(session))
    try:
        asset = await service.transition_state(battery_id, request.target_state, actor=request.actor)
        return {"id": str(asset.id), "state": asset.state}
    except GridMindError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc


@router.post("/{battery_id}/cycles", status_code=201)
async def record_battery_cycle(
    battery_id: UUID,
    request: RecordCycleRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = BatteryService(session)
    cycle = await service.record_cycle(
        battery_id, request.energy_charged_mwh, request.energy_discharged_mwh
    )
    return {"cycle_number": cycle.cycle_number, "degradation_delta_pct": str(cycle.degradation_delta_pct)}
