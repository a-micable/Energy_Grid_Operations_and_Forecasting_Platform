from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from gridmind.domains.operations.decision_support import OperationalDecisionSupport


class TestOperationalDecisionSupport:
    def setup_method(self) -> None:
        self.dss = OperationalDecisionSupport()

    def test_balanced_grid_recommends_monitor(self) -> None:
        rec = self.dss.recommend_balancing_action(Decimal("5"), Decimal("300"), 50.0)
        assert rec.recommended_option == "monitor"

    def test_imbalance_recommends_dispatch(self) -> None:
        rec = self.dss.recommend_balancing_action(Decimal("100"), Decimal("200"), 50.0)
        assert rec.recommended_option in ("dispatch_reserve", "battery_discharge", "load_shed")
        assert len(rec.alternatives) > 0

    def test_critical_frequency_triggers_playbook(self) -> None:
        rec = self.dss.recommend_balancing_action(Decimal("150"), Decimal("50"), 49.90)
        assert len(rec.triggered_playbooks) > 0
        assert len(rec.warnings) > 0

    def test_outage_scheduling_with_conflicts(self) -> None:
        start = datetime(2025, 8, 1, 8, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=4)
        existing = [{"planned_start": start, "planned_end": end}]
        rec = self.dss.recommend_outage_scheduling(start, end, 200, existing, 2000)
        assert len(rec.warnings) > 0

    def test_dispatch_hold_when_unprofitable(self) -> None:
        rec = self.dss.recommend_dispatch_adjustment(
            Decimal("400"), Decimal("500"), Decimal("55"), Decimal("40"), Decimal("10")
        )
        assert rec.recommended_option == "hold"
