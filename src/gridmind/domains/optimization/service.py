from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.db.models.optimization import OptimizationRun, OptimizationScenario
from gridmind.domains.optimization.engine import MultiStageOptimizer, OptimizationStage, ScenarioResult


class OptimizationService:
    def __init__(
        self,
        session: AsyncSession,
        engine: MultiStageOptimizer | None = None,
    ) -> None:
        self._session = session
        self._engine = engine or MultiStageOptimizer()
        self._runs: dict[UUID, OptimizationRun] = {}

    async def start_run(
        self,
        zone_id: UUID,
        run_type: str,
        stages: list[OptimizationStage],
        input_data: dict,
        *,
        timeout_seconds: int = 120,
    ) -> OptimizationRun:
        run = OptimizationRun(
            zone_id=zone_id,
            run_type=run_type,
            status="running",
            started_at=datetime.now(timezone.utc),
            constraints={"stages": [s.stage_name for s in stages]},
            timeout_seconds=timeout_seconds,
        )
        self._session.add(run)
        await self._session.flush()

        result = self._engine.run_multi_stage(stages, input_data)
        final = result.get("final", {})
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.objective_value = Decimal(str(final.get("total_cost", 0)))
        run.solution = result
        run.solver_status = final.get("status", "unknown")
        await self._session.flush()
        return run

    async def run_scenarios(
        self,
        run_id: UUID,
        base_data: dict,
        scenarios: list[dict],
        stage: OptimizationStage,
    ) -> list[OptimizationScenario]:
        results = self._engine.simulate_scenarios(base_data, scenarios, stage)
        db_scenarios: list[OptimizationScenario] = []
        for r in results:
            scenario = OptimizationScenario(
                run_id=run_id,
                scenario_name=r.scenario_name,
                parameters=scenarios[r.rank - 1].get("parameters", {}) if r.rank <= len(scenarios) else {},
                objective_value=r.objective_value,
                solution=r.solution,
                rank=r.rank,
                is_selected=(r.rank == 1),
            )
            self._session.add(scenario)
            db_scenarios.append(scenario)
        await self._session.flush()
        return db_scenarios
