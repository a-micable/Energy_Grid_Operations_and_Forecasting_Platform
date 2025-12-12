from __future__ import annotations

from decimal import Decimal

import pytest

from gridmind.core.exceptions import ValidationError
from gridmind.domains.battery.engine import BatteryOptimizationEngine, BatteryProfile


class TestBatteryEngine:
    def setup_method(self) -> None:
        self.engine = BatteryOptimizationEngine()
        self.profile = BatteryProfile(
            nameplate_capacity_mwh=Decimal("100"),
            usable_capacity_mwh=Decimal("90"),
            max_charge_mw=Decimal("25"),
            max_discharge_mw=Decimal("25"),
            state_of_charge_pct=Decimal("0.50"),
            degradation_pct=Decimal("2.0"),
            round_trip_efficiency=Decimal("0.92"),
            cycle_count=100,
        )

    def test_available_energy_calculation(self) -> None:
        energy = self.profile.available_energy_mwh
        assert energy > Decimal("40")
        assert energy < Decimal("50")

    def test_soc_after_discharge(self) -> None:
        new_soc = self.engine.compute_soc_after_dispatch(
            self.profile, Decimal("25"), 60, is_charging=False
        )
        assert new_soc < self.profile.state_of_charge_pct

    def test_soc_validation_rejects_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            self.engine.validate_soc(Decimal("0.05"))

    def test_degradation_increases_with_dod(self) -> None:
        low_dod = self.engine.compute_degradation(Decimal("0.20"))
        high_dod = self.engine.compute_degradation(Decimal("0.80"))
        assert high_dod > low_dod

    def test_emergency_discharge_insufficient_energy(self) -> None:
        low_soc_profile = BatteryProfile(
            nameplate_capacity_mwh=Decimal("100"),
            usable_capacity_mwh=Decimal("90"),
            max_charge_mw=Decimal("25"),
            max_discharge_mw=Decimal("25"),
            state_of_charge_pct=Decimal("0.05"),
            degradation_pct=Decimal("0"),
            round_trip_efficiency=Decimal("0.92"),
            cycle_count=0,
        )
        with pytest.raises(ValidationError):
            self.engine.plan_emergency_discharge(low_soc_profile, Decimal("50"), 120)
