from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.db.models.balancing import BalancingAction, BalancingSnapshot
from gridmind.db.models.dispatch import DispatchInstruction, DispatchPlan
from gridmind.db.models.forecasting import ForecastPoint, ForecastRun, ForecastVersion
from gridmind.db.models.grid import GenerationResource, GridZone
from gridmind.db.models.outage import OutagePlan


class OperationalQueries:
    """Complex operational queries spanning multiple tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_zone_operational_summary(self, zone_id: UUID) -> dict:
        zone = await self._session.get(GridZone, zone_id)
        if not zone:
            return {}
        resource_count = await self._session.scalar(
            select(func.count()).select_from(GenerationResource).where(
                GenerationResource.zone_id == zone_id
            )
        )
        available_count = await self._session.scalar(
            select(func.count()).select_from(GenerationResource).where(
                and_(GenerationResource.zone_id == zone_id, GenerationResource.is_available.is_(True))
            )
        )
        total_capacity = await self._session.scalar(
            select(func.sum(GenerationResource.capacity_mw)).where(
                GenerationResource.zone_id == zone_id
            )
        )
        renewable_capacity = await self._session.scalar(
            select(func.sum(GenerationResource.capacity_mw)).where(
                and_(GenerationResource.zone_id == zone_id, GenerationResource.is_renewable.is_(True))
            )
        )
        latest_snapshot = await self._session.scalar(
            select(BalancingSnapshot)
            .where(BalancingSnapshot.zone_id == zone_id)
            .order_by(desc(BalancingSnapshot.snapshot_at))
            .limit(1)
        )
        active_outages = await self._session.scalar(
            select(func.count()).select_from(OutagePlan).where(
                and_(
                    OutagePlan.zone_id == zone_id,
                    OutagePlan.status.in_(["approved", "in_progress"]),
                )
            )
        )
        return {
            "zone_code": zone.code,
            "zone_name": zone.name,
            "peak_demand_mw": float(zone.peak_demand_mw),
            "total_capacity_mw": float(total_capacity or 0),
            "renewable_capacity_mw": float(renewable_capacity or 0),
            "resource_count": resource_count or 0,
            "available_resources": available_count or 0,
            "latest_imbalance_mw": float(latest_snapshot.net_imbalance_mw) if latest_snapshot else None,
            "latest_frequency_hz": float(latest_snapshot.frequency_hz) if latest_snapshot else None,
            "active_outages": active_outages or 0,
        }

    async def get_forecast_accuracy_by_type(
        self, zone_id: UUID, start: datetime, end: datetime
    ) -> list[dict]:
        stmt = (
            select(
                ForecastRun.forecast_type,
                func.count(ForecastPoint.id).label("point_count"),
                func.avg(
                    func.abs(ForecastPoint.actual_mw - ForecastPoint.value_mw)
                ).label("mae"),
            )
            .join(ForecastVersion, ForecastVersion.run_id == ForecastRun.id)
            .join(ForecastPoint, ForecastPoint.version_id == ForecastVersion.id)
            .where(
                and_(
                    ForecastRun.zone_id == zone_id,
                    ForecastPoint.timestamp >= start,
                    ForecastPoint.timestamp <= end,
                    ForecastPoint.actual_mw.isnot(None),
                )
            )
            .group_by(ForecastRun.forecast_type)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "forecast_type": row.forecast_type,
                "point_count": row.point_count,
                "mae": float(row.mae) if row.mae else None,
            }
            for row in result
        ]

    async def get_dispatch_cost_summary(
        self, zone_id: UUID, start: datetime, end: datetime
    ) -> dict:
        stmt = (
            select(
                func.sum(DispatchPlan.total_cost).label("total_cost"),
                func.sum(DispatchPlan.total_emissions_kg).label("total_emissions"),
                func.count(DispatchPlan.id).label("plan_count"),
            )
            .where(
                and_(
                    DispatchPlan.zone_id == zone_id,
                    DispatchPlan.horizon_start >= start,
                    DispatchPlan.horizon_end <= end,
                    DispatchPlan.status.in_(["scheduled", "active", "completed"]),
                )
            )
        )
        result = await self._session.execute(stmt)
        row = result.one()
        return {
            "total_cost": float(row.total_cost or 0),
            "total_emissions_kg": float(row.total_emissions or 0),
            "plan_count": row.plan_count or 0,
        }

    async def get_resource_utilization(
        self, resource_id: UUID, start: datetime, end: datetime
    ) -> dict:
        stmt = (
            select(
                func.sum(DispatchInstruction.target_output_mw).label("total_target"),
                func.sum(DispatchInstruction.actual_output_mw).label("total_actual"),
                func.count(DispatchInstruction.id).label("instruction_count"),
                func.avg(DispatchInstruction.target_output_mw).label("avg_target"),
            )
            .where(
                and_(
                    DispatchInstruction.resource_id == resource_id,
                    DispatchInstruction.scheduled_start >= start,
                    DispatchInstruction.scheduled_end <= end,
                )
            )
        )
        result = await self._session.execute(stmt)
        row = result.one()
        resource = await self._session.get(GenerationResource, resource_id)
        capacity = float(resource.capacity_mw) if resource else 0
        hours = (end - start).total_seconds() / 3600
        max_possible = capacity * hours if hours > 0 else 0
        total_target = float(row.total_target or 0)
        return {
            "resource_code": resource.code if resource else None,
            "instruction_count": row.instruction_count or 0,
            "total_target_mwh": total_target,
            "total_actual_mwh": float(row.total_actual or 0),
            "avg_target_mw": float(row.avg_target or 0),
            "utilization_pct": (total_target / max_possible * 100) if max_possible else 0,
        }

    async def get_balancing_action_summary(
        self, zone_id: UUID, start: datetime, end: datetime
    ) -> dict:
        stmt = (
            select(
                BalancingAction.action_type,
                func.count(BalancingAction.id).label("count"),
                func.sum(BalancingAction.target_mw).label("total_mw"),
            )
            .where(
                and_(
                    BalancingAction.zone_id == zone_id,
                    BalancingAction.initiated_at >= start,
                    BalancingAction.initiated_at <= end,
                )
            )
            .group_by(BalancingAction.action_type)
        )
        result = await self._session.execute(stmt)
        by_type = {
            row.action_type: {"count": row.count, "total_mw": float(row.total_mw or 0)}
            for row in result
        }
        total_actions = sum(v["count"] for v in by_type.values())
        return {"by_action_type": by_type, "total_actions": total_actions}

    async def get_upcoming_outages(
        self, zone_id: UUID, days_ahead: int = 30
    ) -> list[dict]:
        from datetime import timedelta, timezone
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        stmt = (
            select(OutagePlan)
            .where(
                and_(
                    OutagePlan.zone_id == zone_id,
                    OutagePlan.planned_start >= now,
                    OutagePlan.planned_start <= end,
                    OutagePlan.status.in_(["scheduled", "approved"]),
                )
            )
            .order_by(OutagePlan.planned_start)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": str(o.id),
                "title": o.title,
                "outage_type": o.outage_type,
                "status": o.status,
                "planned_start": o.planned_start.isoformat(),
                "planned_end": o.planned_end.isoformat(),
                "impact_mw": o.impact_mw,
            }
            for o in result.scalars()
        ]

    async def get_renewable_penetration(
        self, zone_id: UUID, start: datetime, end: datetime
    ) -> dict:
        resources = await self._session.execute(
            select(GenerationResource).where(
                and_(GenerationResource.zone_id == zone_id, GenerationResource.is_renewable.is_(True))
            )
        )
        renewable_ids = [r.id for r in resources.scalars()]
        if not renewable_ids:
            return {"renewable_pct": 0, "renewable_mwh": 0, "total_mwh": 0}
        renewable_output = await self._session.scalar(
            select(func.sum(DispatchInstruction.target_output_mw)).where(
                and_(
                    DispatchInstruction.resource_id.in_(renewable_ids),
                    DispatchInstruction.scheduled_start >= start,
                    DispatchInstruction.scheduled_end <= end,
                )
            )
        )
        total_output = await self._session.scalar(
            select(func.sum(DispatchInstruction.target_output_mw))
            .join(DispatchPlan, DispatchPlan.id == DispatchInstruction.plan_id)
            .where(
                and_(
                    DispatchPlan.zone_id == zone_id,
                    DispatchInstruction.scheduled_start >= start,
                    DispatchInstruction.scheduled_end <= end,
                )
            )
        )
        renewable = float(renewable_output or 0)
        total = float(total_output or 0)
        return {
            "renewable_mwh": renewable,
            "total_mwh": total,
            "renewable_pct": (renewable / total * 100) if total else 0,
        }
