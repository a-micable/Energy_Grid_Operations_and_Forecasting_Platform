from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import numpy as np

from gridmind.core.exceptions import OptimizationError


@dataclass
class Constraint:
    name: str
    constraint_type: str
    parameters: dict[str, Any]
    is_hard: bool = True


@dataclass
class OptimizationStage:
    stage_name: str
    objective: str
    constraints: list[Constraint] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    scenario_id: UUID
    scenario_name: str
    objective_value: Decimal
    solution: dict[str, Any]
    rank: int = 0


class MultiStageOptimizer:
    """Multi-stage optimization with scenario simulation."""

    def __init__(self, timeout_seconds: int = 120) -> None:
        self._timeout = timeout_seconds

    def run_stage(
        self,
        stage: OptimizationStage,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        if stage.objective == "minimize_cost":
            return self._minimize_cost(stage, input_data)
        elif stage.objective == "maximize_renewable":
            return self._maximize_renewable(stage, input_data)
        elif stage.objective == "balance_reserve":
            return self._balance_reserve(stage, input_data)
        raise OptimizationError(f"Unknown objective: {stage.objective}")

    def _minimize_cost(self, stage: OptimizationStage, data: dict[str, Any]) -> dict[str, Any]:
        resources = data.get("resources", [])
        demand = float(data.get("demand_mw", 0))
        if not resources or demand <= 0:
            return {"allocations": {}, "total_cost": 0, "status": "infeasible"}
        sorted_r = sorted(resources, key=lambda r: r.get("marginal_cost", 999))
        remaining = demand
        allocations: dict[str, float] = {}
        total_cost = 0.0
        for r in sorted_r:
            if remaining <= 0:
                break
            cap = float(r.get("max_output_mw", 0))
            dispatch = min(remaining, cap)
            allocations[str(r.get("id", uuid4()))] = dispatch
            total_cost += dispatch * float(r.get("marginal_cost", 0))
            remaining -= dispatch
        return {
            "allocations": allocations,
            "total_cost": total_cost,
            "unmet_demand": remaining,
            "status": "optimal" if remaining == 0 else "partial",
        }

    def _maximize_renewable(self, stage: OptimizationStage, data: dict[str, Any]) -> dict[str, Any]:
        resources = data.get("resources", [])
        demand = float(data.get("demand_mw", 0))
        renewable = [r for r in resources if r.get("is_renewable")]
        non_renewable = [r for r in resources if not r.get("is_renewable")]
        remaining = demand
        allocations: dict[str, float] = {}
        renewable_used = 0.0
        for r in renewable:
            if remaining <= 0:
                break
            cap = float(r.get("max_output_mw", 0))
            dispatch = min(remaining, cap)
            allocations[str(r.get("id"))] = dispatch
            renewable_used += dispatch
            remaining -= dispatch
        for r in non_renewable:
            if remaining <= 0:
                break
            cap = float(r.get("max_output_mw", 0))
            dispatch = min(remaining, cap)
            allocations[str(r.get("id"))] = dispatch
            remaining -= dispatch
        return {
            "allocations": allocations,
            "renewable_pct": renewable_used / demand if demand else 0,
            "status": "optimal" if remaining == 0 else "partial",
        }

    def _balance_reserve(self, stage: OptimizationStage, data: dict[str, Any]) -> dict[str, Any]:
        demand = float(data.get("demand_mw", 0))
        reserve_margin = float(data.get("reserve_margin_pct", 0.15))
        required_reserve = demand * reserve_margin
        available = float(data.get("available_reserve_mw", 0))
        return {
            "required_reserve_mw": required_reserve,
            "available_reserve_mw": available,
            "reserve_adequate": available >= required_reserve,
            "deficit_mw": max(0, required_reserve - available),
            "status": "optimal" if available >= required_reserve else "infeasible",
        }

    def run_multi_stage(
        self,
        stages: list[OptimizationStage],
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        current_data = dict(input_data)
        stage_results: dict[str, dict] = {}
        for stage in stages:
            result = self.run_stage(stage, current_data)
            stage_results[stage.stage_name] = result
            current_data.update(result)
        return {"stages": stage_results, "final": current_data}

    def simulate_scenarios(
        self,
        base_data: dict[str, Any],
        scenarios: list[dict[str, Any]],
        stage: OptimizationStage,
    ) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        for i, scenario in enumerate(scenarios):
            merged = {**base_data, **scenario.get("parameters", {})}
            result = self.run_stage(stage, merged)
            obj_val = Decimal(str(result.get("total_cost", result.get("renewable_pct", 0))))
            results.append(
                ScenarioResult(
                    scenario_id=uuid4(),
                    scenario_name=scenario.get("name", f"scenario_{i}"),
                    objective_value=obj_val,
                    solution=result,
                    rank=i,
                )
            )
        results.sort(key=lambda r: r.objective_value)
        for i, r in enumerate(results):
            r.rank = i + 1
        return results
