from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.core.events import DomainEvent, InMemoryEventBus
from gridmind.core.exceptions import NotFoundError, ValidationError
from gridmind.core.types import ForecastHorizon, ForecastType
from gridmind.db.models.forecasting import ForecastPoint, ForecastRevision, ForecastRun, ForecastVersion
from gridmind.db.repositories.forecasting import (
    ForecastPointRepository,
    ForecastRevisionRepository,
    ForecastRunRepository,
    ForecastVersionRepository,
)
from gridmind.domains.forecasting.engine import ForecastEngine, ForecastPointData
from gridmind.services.audit import AuditService

logger = structlog.get_logger(__name__)


class ForecastingService:
    def __init__(
        self,
        session: AsyncSession,
        engine: ForecastEngine | None = None,
        event_bus: InMemoryEventBus | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._session = session
        self._engine = engine or ForecastEngine()
        self._run_repo = ForecastRunRepository(session)
        self._version_repo = ForecastVersionRepository(session)
        self._point_repo = ForecastPointRepository(session)
        self._revision_repo = ForecastRevisionRepository(session)
        self._event_bus = event_bus
        self._audit = audit

    async def create_forecast_run(
        self,
        zone_id: UUID,
        forecast_type: ForecastType,
        horizon: ForecastHorizon,
        *,
        model_name: str = "gridmind-ensemble-v3",
        model_version: str = "3.2.1",
        base_load_mw: float = 1500.0,
        hours: int = 48,
        actor: str = "system",
    ) -> ForecastRun:
        run = ForecastRun(
            zone_id=zone_id,
            forecast_type=forecast_type.value,
            horizon=horizon.value,
            model_name=model_name,
            model_version=model_version,
            status="running",
            started_at=datetime.now(timezone.utc),
            parameters={"base_load_mw": base_load_mw, "hours": hours},
        )
        await self._run_repo.add(run)

        start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        if forecast_type == ForecastType.DEMAND:
            point_data = self._engine.generate_hourly_demand(base_load_mw, start, hours)
        elif forecast_type in (ForecastType.SOLAR, ForecastType.WIND, ForecastType.RENEWABLE):
            point_data = self._engine.generate_renewable_output(
                base_load_mw, forecast_type, start, hours
            )
        else:
            raise ValidationError(f"Unsupported forecast type: {forecast_type}")

        version = ForecastVersion(
            run_id=run.id,
            version_number=1,
            is_current=True,
            valid_from=start,
            valid_to=start + __import__("datetime").timedelta(hours=hours),
            confidence_level=Decimal("0.95"),
            published_at=datetime.now(timezone.utc),
        )
        await self._version_repo.add(version)

        points = [
            ForecastPoint(
                version_id=version.id,
                timestamp=p.timestamp,
                value_mw=p.value_mw,
                lower_bound_mw=p.lower_bound_mw,
                upper_bound_mw=p.upper_bound_mw,
            )
            for p in point_data
        ]
        await self._point_repo.bulk_insert(points)

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.metrics = {"point_count": len(points)}
        await self._session.flush()

        if self._audit:
            await self._audit.record(
                "forecast_run", run.id, "created", actor, after_state={"status": "completed"}
            )
        if self._event_bus:
            await self._event_bus.publish(
                DomainEvent(
                    event_type="forecast.created",
                    aggregate_type="forecast_run",
                    aggregate_id=run.id,
                    payload={"zone_id": str(zone_id), "forecast_type": forecast_type.value},
                )
            )
        return run

    async def revise_forecast(
        self,
        run_id: UUID,
        revised_points: list[ForecastPointData],
        *,
        reason: str,
        revised_by: str,
        force: bool = False,
    ) -> ForecastVersion:
        run = await self._run_repo.get_by_id_or_raise(run_id)
        current = await self._version_repo.get_current_for_run(run_id)
        if not current:
            raise NotFoundError(f"No current version for run {run_id}")

        current_points = await self._point_repo.get_range(
            current.id, current.valid_from, current.valid_to
        )
        prev_data = [
            ForecastPointData(
                timestamp=p.timestamp,
                value_mw=p.value_mw,
                lower_bound_mw=p.lower_bound_mw,
                upper_bound_mw=p.upper_bound_mw,
            )
            for p in current_points
        ]

        try:
            delta = self._engine.validate_revision(run_id, prev_data, revised_points)
        except Exception:
            if not force:
                raise
            delta = self._engine.compute_revision_delta(prev_data, revised_points)

        new_version = ForecastVersion(
            run_id=run_id,
            version_number=current.version_number + 1,
            valid_from=current.valid_from,
            valid_to=current.valid_to,
            confidence_level=current.confidence_level,
            revision_reason=reason,
            published_at=datetime.now(timezone.utc),
        )
        await self._version_repo.add(new_version)
        await self._version_repo.supersede_current(run_id, new_version)

        points = [
            ForecastPoint(
                version_id=new_version.id,
                timestamp=p.timestamp,
                value_mw=p.value_mw,
                lower_bound_mw=p.lower_bound_mw,
                upper_bound_mw=p.upper_bound_mw,
            )
            for p in revised_points
        ]
        await self._point_repo.bulk_insert(points)

        revisions = await self._revision_repo.list_for_version(current.id)
        revision = ForecastRevision(
            version_id=new_version.id,
            previous_version_id=current.id,
            revision_number=len(revisions) + 1,
            delta_pct=delta,
            reason=reason,
            revised_by=revised_by,
            drift_flagged=delta > Decimal("0.15"),
        )
        await self._revision_repo.add(revision)

        if self._audit:
            await self._audit.record(
                "forecast_version",
                new_version.id,
                "revised",
                revised_by,
                before_state={"version": current.version_number},
                after_state={"version": new_version.version_number, "delta_pct": str(delta)},
                reason=reason,
            )
        return new_version
