from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from gridmind.core.types import BalancingMode
from gridmind.domains.balancing.engine import BalancingEngine


class TestBalancingEngine:
    def setup_method(self) -> None:
        self.engine = BalancingEngine(reserve_margin_pct=0.15)

    def test_balanced_state_no_intervention(self) -> None:
        state = self.engine.compute_state(
            Decimal("1000"), Decimal("1000"), Decimal("200")
        )
        assert state.is_balanced
        assert not state.needs_intervention

    def test_imbalanced_state_needs_intervention(self) -> None:
        state = self.engine.compute_state(
            Decimal("900"), Decimal("1000"), Decimal("200")
        )
        assert not state.is_balanced
        assert state.needs_intervention

    def test_required_reserve_calculation(self) -> None:
        reserve = self.engine.compute_required_reserve(Decimal("2000"))
        assert reserve == Decimal("300.0")

    def test_balancing_actions_for_deficit(self) -> None:
        state = self.engine.compute_state(
            Decimal("900"), Decimal("1000"), Decimal("200")
        )
        resources = [
            {"id": uuid4(), "available_mw": 50, "dispatch_priority": 10, "marginal_cost": 40},
            {"id": uuid4(), "available_mw": 100, "dispatch_priority": 20, "marginal_cost": 50},
        ]
        actions = self.engine.plan_balancing_actions(state, resources)
        assert len(actions) > 0
        assert actions[0].action_type == "increase_output"
        total = sum(a.target_mw for a in actions)
        assert total >= Decimal("50")

    def test_emergency_load_shed_when_insufficient(self) -> None:
        state = self.engine.compute_state(
            Decimal("800"), Decimal("1000"), Decimal("50")
        )
        resources = [{"id": uuid4(), "available_mw": 50, "dispatch_priority": 10, "marginal_cost": 40}]
        actions = self.engine.plan_balancing_actions(
            state, resources, mode=BalancingMode.EMERGENCY
        )
        load_shed = [a for a in actions if a.action_type == "load_shed"]
        assert len(load_shed) > 0
