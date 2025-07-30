from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import structlog

from gridmind.core.exceptions import ValidationError
from gridmind.core.types import BalancingMode

logger = structlog.get_logger(__name__)

NOMINAL_FREQUENCY_HZ = Decimal("50.0")
FREQUENCY_DEADBAND_HZ = Decimal("0.05")


@dataclass
class BalancingState:
    supply_mw: Decimal
    demand_mw: Decimal
    reserve_available_mw: Decimal
    frequency_hz: Decimal

    @property
    def net_imbalance_mw(self) -> Decimal:
        return self.supply_mw - self.demand_mw

    @property
    def is_balanced(self) -> bool:
        return abs(self.net_imbalance_mw) < Decimal("10")

    @property
    def needs_intervention(self) -> bool:
        freq_dev = abs(self.frequency_hz - NOMINAL_FREQUENCY_HZ)
        return freq_dev > FREQUENCY_DEADBAND_HZ or abs(self.net_imbalance_mw) > Decimal("50")


@dataclass
class BalancingActionPlan:
    resource_id: UUID | None
    action_type: str
    target_mw: Decimal
    priority: int
    mode: BalancingMode
    reason: str


class BalancingEngine:
    """Real-time and scheduled grid balancing calculations."""

    def __init__(self, reserve_margin_pct: float = 0.15) -> None:
        self._reserve_margin_pct = Decimal(str(reserve_margin_pct))

    def compute_state(
        self,
        supply_mw: Decimal,
        demand_mw: Decimal,
        reserve_mw: Decimal,
        frequency_hz: Decimal | None = None,
    ) -> BalancingState:
        if supply_mw < 0 or demand_mw < 0:
            raise ValidationError("Supply and demand must be non-negative")
        if frequency_hz is None:
            imbalance = supply_mw - demand_mw
            freq_adjust = imbalance / Decimal("1000") * Decimal("0.1")
            frequency_hz = NOMINAL_FREQUENCY_HZ + freq_adjust
        return BalancingState(
            supply_mw=supply_mw,
            demand_mw=demand_mw,
            reserve_available_mw=reserve_mw,
            frequency_hz=frequency_hz,
        )

    def compute_required_reserve(self, peak_demand_mw: Decimal) -> Decimal:
        return peak_demand_mw * self._reserve_margin_pct

    def plan_balancing_actions(
        self,
        state: BalancingState,
        available_resources: list[dict],
        mode: BalancingMode = BalancingMode.REALTIME,
    ) -> list[BalancingActionPlan]:
        if not state.needs_intervention:
            return []

        imbalance = state.net_imbalance_mw
        actions: list[BalancingActionPlan] = []
        remaining = abs(imbalance)
        need_increase = imbalance < 0

        sorted_resources = sorted(
            available_resources,
            key=lambda r: (r.get("dispatch_priority", 100), r.get("marginal_cost", 999)),
        )

        for resource in sorted_resources:
            if remaining <= 0:
                break
            capacity = Decimal(str(resource.get("available_mw", 0)))
            if capacity <= 0:
                continue
            dispatch = min(remaining, capacity)
            action_type = "increase_output" if need_increase else "decrease_output"
            actions.append(
                BalancingActionPlan(
                    resource_id=resource.get("id"),
                    action_type=action_type,
                    target_mw=dispatch,
                    priority=resource.get("dispatch_priority", 100),
                    mode=mode,
                    reason=f"Correct {'deficit' if need_increase else 'surplus'} of {imbalance} MW",
                )
            )
            remaining -= dispatch

        if remaining > 0 and mode == BalancingMode.EMERGENCY:
            actions.append(
                BalancingActionPlan(
                    resource_id=None,
                    action_type="load_shed",
                    target_mw=remaining,
                    priority=0,
                    mode=BalancingMode.EMERGENCY,
                    reason=f"Emergency load shed for {remaining} MW deficit",
                )
            )
        return actions
