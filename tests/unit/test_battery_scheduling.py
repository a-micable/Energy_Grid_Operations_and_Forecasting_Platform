from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from gridmind.domains.battery.engine import BatteryProfile
from gridmind.domains.battery.scheduling import BatterySchedulingService


class TestBatterySchedulingService:
    def setup_method(self) -> None:
        self.service = BatterySchedulingService()
        self.battery_id = uuid4()
        self.profile = BatteryProfile(
            nameplate_capacity_mwh=Decimal("100"),
            usable_capacity_mwh=Decimal("90"),
            max_charge_mw=Decimal("25"),
            max_discharge_mw=Decimal("25"),
            state_of_charge_pct=Decimal("0.50"),
            degradation_pct=Decimal("1.0"),
            round_trip_efficiency=Decimal("0.92"),
            cycle_count=50,
        )

    def test_arbitrage_planning(self) -> None:
        base = datetime(2025, 7, 1, tzinfo=timezone.utc)
        prices = [(base.replace(hour=h), Decimal(str(30 + h * 2))) for h in range(24)]
        plan = self.service.plan_arbitrage(self.battery_id, self.profile, prices)
        assert isinstance(plan.schedules, list)

    def test_validate_feasibility(self) -> None:
        from gridmind.domains.battery.engine import DispatchSchedule
        schedules = [
            DispatchSchedule(action="discharge", power_mw=Decimal("20"), duration_minutes=60),
            DispatchSchedule(action="charge", power_mw=Decimal("15"), duration_minutes=60),
        ]
        issues = self.service.validate_schedule_feasibility(self.profile, schedules)
        assert isinstance(issues, list)

    def test_cycle_impact(self) -> None:
        from gridmind.domains.battery.engine import DispatchSchedule
        schedules = [
            DispatchSchedule(action="discharge", power_mw=Decimal("25"), duration_minutes=120),
        ]
        impact = self.service.compute_cycle_impact(self.profile, schedules)
        assert impact["total_discharge_mwh"] > 0
        assert impact["depth_of_discharge_pct"] > 0
