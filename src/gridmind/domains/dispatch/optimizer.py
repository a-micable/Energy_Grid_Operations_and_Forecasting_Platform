from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

import numpy as np
from scipy.optimize import linprog

from gridmind.core.exceptions import DispatchConflictError, OptimizationError


@dataclass
class ResourceOffer:
    resource_id: UUID
    resource_type: str
    min_output_mw: Decimal
    max_output_mw: Decimal
    marginal_cost: Decimal
    emission_rate: Decimal
    dispatch_priority: int
    ramp_rate_mw_per_min: Decimal


@dataclass
class DispatchAllocation:
    resource_id: UUID
    output_mw: Decimal
    cost: Decimal
    emissions_kg: Decimal
    start: datetime
    end: datetime


@dataclass
class OptimizationResult:
    allocations: list[DispatchAllocation]
    total_cost: Decimal
    total_emissions_kg: Decimal
    total_output_mw: Decimal
    unmet_demand_mw: Decimal
    solver_status: str


class DispatchOptimizer:
    """Economic dispatch with emission constraints."""

    def __init__(
        self,
        max_emissions_kg: Decimal | None = None,
        emission_price_per_kg: Decimal = Decimal("0.05"),
    ) -> None:
        self._max_emissions = max_emissions_kg
        self._emission_price = emission_price_per_kg

    def optimize(
        self,
        demand_mw: Decimal,
        resources: list[ResourceOffer],
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> OptimizationResult:
        if not resources:
            raise OptimizationError("No resources available for dispatch")
        if demand_mw <= 0:
            raise OptimizationError("Demand must be positive")

        n = len(resources)
        costs = []
        for r in resources:
            effective_cost = float(r.marginal_cost) + float(r.emission_rate) * float(self._emission_price)
            costs.append(effective_cost)

        bounds = [(float(r.min_output_mw), float(r.max_output_mw)) for r in resources]
        A_eq = [np.ones(n)]
        b_eq = [float(demand_mw)]

        constraints = []
        if self._max_emissions is not None:
            A_ub = [np.array([float(r.emission_rate) for r in resources])]
            b_ub = [float(self._max_emissions)]
            result = linprog(costs, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
        else:
            result = linprog(costs, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

        if not result.success:
            sorted_resources = sorted(resources, key=lambda r: (r.dispatch_priority, r.marginal_cost))
            return self._priority_dispatch(demand_mw, sorted_resources, horizon_start, horizon_end)

        allocations: list[DispatchAllocation] = []
        total_cost = Decimal("0")
        total_emissions = Decimal("0")
        total_output = Decimal("0")

        for i, r in enumerate(resources):
            output = Decimal(str(round(result.x[i], 4)))
            if output > 0:
                cost = output * r.marginal_cost
                emissions = output * r.emission_rate
                allocations.append(
                    DispatchAllocation(
                        resource_id=r.resource_id,
                        output_mw=output,
                        cost=cost,
                        emissions_kg=emissions,
                        start=horizon_start,
                        end=horizon_end,
                    )
                )
                total_cost += cost
                total_emissions += emissions
                total_output += output

        unmet = max(Decimal("0"), demand_mw - total_output)
        return OptimizationResult(
            allocations=allocations,
            total_cost=total_cost,
            total_emissions_kg=total_emissions,
            total_output_mw=total_output,
            unmet_demand_mw=unmet,
            solver_status="optimal" if unmet == 0 else "partial",
        )

    def _priority_dispatch(
        self,
        demand_mw: Decimal,
        resources: list[ResourceOffer],
        start: datetime,
        end: datetime,
    ) -> OptimizationResult:
        remaining = demand_mw
        allocations: list[DispatchAllocation] = []
        total_cost = Decimal("0")
        total_emissions = Decimal("0")
        total_output = Decimal("0")

        for r in resources:
            if remaining <= 0:
                break
            dispatch = min(remaining, r.max_output_mw)
            dispatch = max(dispatch, r.min_output_mw) if dispatch >= r.min_output_mw else Decimal("0")
            if dispatch <= 0:
                continue
            cost = dispatch * r.marginal_cost
            emissions = dispatch * r.emission_rate
            allocations.append(
                DispatchAllocation(
                    resource_id=r.resource_id,
                    output_mw=dispatch,
                    cost=cost,
                    emissions_kg=emissions,
                    start=start,
                    end=end,
                )
            )
            total_cost += cost
            total_emissions += emissions
            total_output += dispatch
            remaining -= dispatch

        return OptimizationResult(
            allocations=allocations,
            total_cost=total_cost,
            total_emissions_kg=total_emissions,
            total_output_mw=total_output,
            unmet_demand_mw=max(Decimal("0"), remaining),
            solver_status="priority_fallback",
        )

    def detect_conflicts(
        self,
        new_allocation: DispatchAllocation,
        existing: list[DispatchAllocation],
    ) -> list[tuple[UUID, UUID]]:
        conflicts: list[tuple[UUID, UUID]] = []
        for ex in existing:
            if ex.resource_id != new_allocation.resource_id:
                continue
            if new_allocation.start < ex.end and new_allocation.end > ex.start:
                conflicts.append((new_allocation.resource_id, ex.resource_id))
        return conflicts
