from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.api.deps import get_session
from gridmind.core.exceptions import GridMindError
from gridmind.domains.grid.service import GridZoneService

router = APIRouter(prefix="/grid", tags=["grid"])


class CreateZoneRequest(BaseModel):
    code: str
    name: str
    region: str
    peak_demand_mw: Decimal
    timezone: str = "UTC"


class ZoneResponse(BaseModel):
    id: UUID
    code: str
    name: str
    region: str
    peak_demand_mw: Decimal
    is_active: bool

    model_config = {"from_attributes": True}


@router.post("/zones", response_model=ZoneResponse, status_code=201)
async def create_zone(request: CreateZoneRequest, session: AsyncSession = Depends(get_session)) -> ZoneResponse:
    svc = GridZoneService(session)
    try:
        zone = await svc.create_zone(
            request.code, request.name, request.region, request.peak_demand_mw,
            timezone=request.timezone,
        )
        return ZoneResponse.model_validate(zone)
    except GridMindError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get("/zones/{zone_id}/capacity")
async def get_capacity_summary(zone_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    svc = GridZoneService(session)
    try:
        return await svc.get_zone_capacity_summary(zone_id)
    except GridMindError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
