from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.core.types import BalancingMode, ForecastHorizon, ForecastType
from gridmind.domains.analytics.historical import HistoricalAnalyzer, TimeSeriesPoint
from gridmind.domains.analytics.reporting import OperationalReportGenerator
from gridmind.domains.balancing.service import BalancingService
from gridmind.domains.compliance.rules_engine import ComplianceRulesEngine
from gridmind.domains.dispatch.optimizer import DispatchOptimizer, ResourceOffer
from gridmind.domains.forecasting.service import ForecastingService
from gridmind.services.audit import AuditService

logger = structlog.get_logger(__name__)


class OperationalCoordinator:
    """Coordinate cross-domain operational workflows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditService(session)
        self._forecast_svc = ForecastingService(session, audit=self._audit)
        self._balancing_svc = BalancingService(session, audit=self._audit)
        self._compliance = ComplianceRulesEngine()
        self._analyzer = HistoricalAnalyzer()
        self._reporter = OperationalReportGenerator()
        self._dispatch_optimizer = DispatchOptimizer()

    async def run_daily_operations_cycle(
        self,
        zone_id: UUID,
        resources: list[dict],
        *,
        base_demand_mw: float = 2000.0,
        actor: str = "coordinator",
    ) -> dict[str, Any]:
        """Execute full daily operations cycle: forecast → dispatch → balance → compliance."""
        results: dict[str, Any] = {"zone_id": str(zone_id), "steps": {}}

        # Step 1: Generate demand forecast
        logger.info("daily_cycle_forecast_start", zone_id=str(zone_id))
        forecast_run = await self._forecast_svc.create_forecast_run(
            zone_id, ForecastType.DEMAND, ForecastHorizon.HOURLY,
            base_load_mw=base_demand_mw, hours=24, actor=actor,
        )
        results["steps"]["forecast"] = {"run_id": str(forecast_run.id), "status": forecast_run.status}

        # Step 2: Optimize dispatch
        demand_mw = Decimal(str(base_demand_mw))
        offers = [
            ResourceOffer(
                resource_id=r["id"],
                resource_type=r.get("type", "gas_plant"),
                min_output_mw=Decimal(str(r.get("min_mw", 0))),
                max_output_mw=Decimal(str(r.get("max_mw", 100))),
                marginal_cost=Decimal(str(r.get("cost", 50))),
                emission_rate=Decimal(str(r.get("emissions", 0))),
                dispatch_priority=r.get("priority", 100),
                ramp_rate_mw_per_min=Decimal("10"),
            )
            for r in resources
        ]
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=1)
        dispatch_result = self._dispatch_optimizer.optimize(demand_mw, offers, start, end)
        results["steps"]["dispatch"] = {
            "total_output_mw": float(dispatch_result.total_output_mw),
            "total_cost": float(dispatch_result.total_cost),
            "solver_status": dispatch_result.solver_status,
        }

        # Step 3: Record balancing snapshot
        supply = dispatch_result.total_output_mw
        snapshot = await self._balancing_svc.record_snapshot(
            zone_id, supply, demand_mw, Decimal("300"), mode=BalancingMode.SCHEDULED,
        )
        results["steps"]["balancing"] = {
            "imbalance_mw": float(snapshot.net_imbalance_mw),
            "frequency_hz": float(snapshot.frequency_hz),
        }

        # Step 4: Compliance check
        compliance_ctx = {
            "reserve_mw": 300,
            "peak_demand_mw": float(base_demand_mw),
            "total_emissions_kg": float(dispatch_result.total_emissions_kg),
            "frequency_hz": float(snapshot.frequency_hz),
        }
        compliance_results = self._compliance.evaluate_all(compliance_ctx)
        violations = self._compliance.get_violations(compliance_results)
        results["steps"]["compliance"] = {
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": [{"rule": v.rule_id, "message": v.message} for v in violations],
        }

        await self._audit.record(
            "operational_cycle", zone_id, "daily_cycle_completed", actor,
            after_state=results["steps"],
        )
        return results

    async def generate_zone_health_report(
        self,
        zone_id: UUID,
        demand_history: list[tuple[datetime, float]],
        supply_history: list[tuple[datetime, float]],
    ) -> dict[str, Any]:
        demand_points = [TimeSeriesPoint(ts, v) for ts, v in demand_history]
        supply_points = [TimeSeriesPoint(ts, v) for ts, v in supply_history]
        if not demand_points:
            return {"error": "No demand history provided"}
        start = demand_points[0].timestamp
        end = demand_points[-1].timestamp
        report = self._reporter.generate_daily_operations_report(
            demand_points, supply_points, start, end
        )
        return {
            "report_id": report.report_id,
            "sections": report.sections,
            "recommendations": report.recommendations,
        }
