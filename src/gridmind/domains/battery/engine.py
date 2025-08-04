from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from gridmind.core.exceptions import ValidationError
from gridmind.core.types import BatteryState


@dataclass
class BatteryProfile:
    nameplate_capacity_mwh: Decimal
    usable_capacity_mwh: Decimal
    max_charge_mw: Decimal
    max_discharge_mw: Decimal
    state_of_charge_pct: Decimal
    degradation_pct: Decimal
    round_trip_efficiency: Decimal
    cycle_count: int

    @property
    def available_energy_mwh(self) -> Decimal:
        effective = self.usable_capacity_mwh * (Decimal("1") - self.degradation_pct / Decimal("100"))
        return effective * self.state_of_charge_pct

    @property
    def available_headroom_mwh(self) -> Decimal:
        effective = self.usable_capacity_mwh * (Decimal("1") - self.degradation_pct / Decimal("100"))
        return effective * (Decimal("1") - self.state_of_charge_pct)


@dataclass
class DispatchSchedule:
    action: str
    power_mw: Decimal
    duration_minutes: int
    target_soc_pct: Decimal | None = None
    is_emergency: bool = False


class BatteryOptimizationEngine:
    """Battery scheduling and degradation modeling."""

    DEGRADATION_PER_CYCLE_PCT = Decimal("0.001")

    def __init__(
        self,
        min_soc_pct: Decimal = Decimal("0.10"),
        max_soc_pct: Decimal = Decimal("0.95"),
    ) -> None:
        self._min_soc = min_soc_pct
        self._max_soc = max_soc_pct

    def validate_soc(self, soc_pct: Decimal) -> None:
        if soc_pct < self._min_soc or soc_pct > self._max_soc:
            raise ValidationError(
                f"SOC {soc_pct} outside allowed range [{self._min_soc}, {self._max_soc}]"
            )

    def compute_soc_after_dispatch(
        self,
        profile: BatteryProfile,
        power_mw: Decimal,
        duration_minutes: int,
        *,
        is_charging: bool,
    ) -> Decimal:
        hours = Decimal(str(duration_minutes)) / Decimal("60")
        energy_mwh = power_mw * hours
        effective_capacity = profile.usable_capacity_mwh * (
            Decimal("1") - profile.degradation_pct / Decimal("100")
        )
        if effective_capacity == 0:
            return profile.state_of_charge_pct
        if is_charging:
            energy_mwh *= profile.round_trip_efficiency
            delta_soc = energy_mwh / effective_capacity
            new_soc = profile.state_of_charge_pct + delta_soc
        else:
            delta_soc = energy_mwh / effective_capacity
            new_soc = profile.state_of_charge_pct - delta_soc
        return max(self._min_soc, min(self._max_soc, new_soc))

    def compute_degradation(self, depth_of_discharge_pct: Decimal) -> Decimal:
        base = self.DEGRADATION_PER_CYCLE_PCT
        stress_factor = Decimal("1") + depth_of_discharge_pct
        return base * stress_factor

    def optimize_arbitrage_schedule(
        self,
        profile: BatteryProfile,
        price_forecast: list[tuple[datetime, Decimal]],
        *,
        horizon_hours: int = 24,
    ) -> list[DispatchSchedule]:
        if len(price_forecast) < 2:
            return []
        sorted_prices = sorted(price_forecast[:horizon_hours], key=lambda x: x[1])
        charge_slots = sorted_prices[: len(sorted_prices) // 3]
        discharge_slots = sorted(price_forecast[:horizon_hours], key=lambda x: x[1], reverse=True)[
            : len(sorted_prices) // 3
        ]
        schedule: list[DispatchSchedule] = []
        for ts, _ in charge_slots:
            if profile.state_of_charge_pct < self._max_soc - Decimal("0.05"):
                schedule.append(
                    DispatchSchedule(
                        action="charge",
                        power_mw=min(profile.max_charge_mw, Decimal("50")),
                        duration_minutes=60,
                        target_soc_pct=self._max_soc,
                    )
                )
        for ts, _ in discharge_slots:
            if profile.state_of_charge_pct > self._min_soc + Decimal("0.05"):
                schedule.append(
                    DispatchSchedule(
                        action="discharge",
                        power_mw=min(profile.max_discharge_mw, Decimal("50")),
                        duration_minutes=60,
                        target_soc_pct=self._min_soc + Decimal("0.10"),
                    )
                )
        return schedule

    def plan_emergency_discharge(
        self, profile: BatteryProfile, required_mw: Decimal, duration_minutes: int
    ) -> DispatchSchedule:
        available_power = min(profile.max_discharge_mw, required_mw)
        hours = Decimal(str(duration_minutes)) / Decimal("60")
        energy_needed = required_mw * hours
        if energy_needed > profile.available_energy_mwh:
            raise ValidationError("Insufficient stored energy for emergency discharge")
        return DispatchSchedule(
            action="emergency_discharge",
            power_mw=available_power,
            duration_minutes=duration_minutes,
            is_emergency=True,
        )
