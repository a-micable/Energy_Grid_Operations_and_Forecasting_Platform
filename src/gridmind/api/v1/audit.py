from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.api.deps import get_session
from gridmind.domains.audit.service import AuditDomainService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/entities/{entity_type}/{entity_id}/history")
async def get_entity_history(
    entity_type: str,
    entity_id: UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=100, le=500),
) -> list[dict]:
    from gridmind.db.repositories.audit import AuditEntryRepository
    repo = AuditEntryRepository(session)
    entries = await repo.get_entity_history(entity_type, entity_id, limit=limit)
    return [
        {
            "id": str(e.id),
            "action": e.action,
            "actor": e.actor,
            "occurred_at": e.occurred_at.isoformat(),
            "before_state": e.before_state,
            "after_state": e.after_state,
            "reason": e.reason,
        }
        for e in entries
    ]


@router.get("/entities/{entity_type}/{entity_id}/reconstruct")
async def reconstruct_entity(
    entity_type: str,
    entity_id: UUID,
    at: datetime,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = AuditDomainService(session)
    state = await service.reconstruct_entity(entity_type, entity_id, at)
    if state is None:
        raise HTTPException(status_code=404, detail="No state found at requested time")
    return {"entity_type": entity_type, "entity_id": str(entity_id), "at": at.isoformat(), "state": state}


@router.post("/compliance-reports", status_code=201)
async def generate_compliance_report(
    report_type: str,
    period_start: datetime,
    period_end: datetime,
    generated_by: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = AuditDomainService(session)
    report = await service.generate_compliance_report(
        report_type, period_start, period_end, generated_by=generated_by
    )
    return {
        "id": str(report.id),
        "report_type": report.report_type,
        "findings": report.findings,
        "status": report.status,
    }
