from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.db.models.audit import AuditEntry, ComplianceReport
from gridmind.db.repositories.audit import AuditEntryRepository, ComplianceReportRepository
from gridmind.domains.audit.reconstructor import HistoricalReconstructor


class AuditDomainService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._entry_repo = AuditEntryRepository(session)
        self._report_repo = ComplianceReportRepository(session)

    async def generate_compliance_report(
        self,
        report_type: str,
        period_start: datetime,
        period_end: datetime,
        *,
        generated_by: str,
    ) -> ComplianceReport:
        entries = await self._entry_repo.get_timeline(period_start, period_end)
        findings: list[dict] = []
        manual_overrides = [e for e in entries if e.action == "manual_override"]
        if manual_overrides:
            findings.append({
                "severity": "info",
                "category": "manual_overrides",
                "count": len(manual_overrides),
                "description": f"{len(manual_overrides)} manual overrides during period",
            })
        drift_events = [e for e in entries if "drift" in (e.reason or "").lower()]
        if drift_events:
            findings.append({
                "severity": "warning",
                "category": "forecast_drift",
                "count": len(drift_events),
                "description": "Forecast drift events detected",
            })
        report = ComplianceReport(
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            status="completed",
            generated_by=generated_by,
            content={"total_entries": len(entries), "period_days": (period_end - period_start).days},
            findings=findings,
        )
        await self._report_repo.add(report)
        return report

    async def reconstruct_entity(
        self, entity_type: str, entity_id: UUID, at: datetime
    ) -> dict | None:
        entries_raw = await self._entry_repo.get_entity_history(entity_type, entity_id, limit=1000)
        entries = [
            {
                "occurred_at": e.occurred_at,
                "action": e.action,
                "actor": e.actor,
                "entity_type": e.entity_type,
                "entity_id": str(e.entity_id),
                "before_state": e.before_state,
                "after_state": e.after_state,
            }
            for e in entries_raw
        ]
        reconstructor = HistoricalReconstructor(entries)
        return reconstructor.reconstruct_at(at)
