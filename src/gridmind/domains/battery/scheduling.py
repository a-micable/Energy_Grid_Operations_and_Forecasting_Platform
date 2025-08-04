from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from gridmind.core.exceptions import SchedulingConflictError, ValidationError
from gridmind.domains.battery.engine import BatteryOptimizationEngine, BatteryProfile, DispatchSchedule
from gridmind.domains.scheduling.engine import ScheduleSlot, SchedulingEngine


@dataclass
class BatterySchedulePlan:
    battery_id: UUID
    schedules: list[DispatchSchedule]
    total_energy_mwh: Decimal
    estimated_revenue: Decimal
    conflicts_resolved: int


class BatterySchedulingService:
    """Advanced battery scheduling with conflict resolution."""

    def __init__(self) -> None:
        self._engine = BatteryOptimizationEngine()
        self._scheduler = SchedulingEngine()

    def plan_arbitrage(
        self,
        battery_id: UUID,
        profile: BatteryProfile,
        price_forecast: list[tuple[datetime, Decimal]],
        *,
        horizon_hours: int = 24,
    ) -> BatterySchedulePlan:
        schedules = self._engine.optimize_arbitrage_schedule(
            profile, price_forecast, horizon_hours=horizon_hours
        )
        total_energy = sum(
            s.power_mw * Decimal(str(s.duration_minutes)) / Decimal("60")
            for s in schedules
        )
        estimated_revenue = Decimal("0")
        for i, schedule in enumerate(schedules):
            if i < len(price_forecast) and schedule.action == "discharge":
                estimated_revenue += schedule.power_mw * price_forecast[i][1] * Decimal(str(schedule.duration_minutes)) / Decimal("60")
        return BatterySchedulePlan(
            battery_id=battery_id,
            schedules=schedules,
            total_energy_mwh=total_energy,
            estimated_revenue=estimated_revenue,
            conflicts_resolved=0,
        )

    def merge_with_existing(
        self,
        new_schedules: list[DispatchSchedule],
        existing_slots: list[ScheduleSlot],
        battery_id: UUID,
    ) -> tuple[list[DispatchSchedule], int]:
        new_slots: list[ScheduleSlot] = []
        base_time = datetime.utcnow()
        for i, sched in enumerate(new_schedules):
            start = base_time + timedelta(hours=i)
            end = start + timedelta(minutes=sched.duration_minutes)
            new_slots.append(ScheduleSlot(
                start=start, end=end,
                resource_id=battery_id,
                activity_type=sched.action,
                priority=0 if sched.is_emergency else 50,
            ))
        all_slots = existing_slots + new_slots
        conflicts = self._scheduler.detect_conflicts(all_slots)
        if conflicts:
            resolved, remaining = self._scheduler.optimize_schedule(all_slots)
            if remaining:
                raise SchedulingConflictError(
                    f"Unable to resolve {len(remaining)} battery scheduling conflicts"
                )
            return new_schedules, len(conflicts)
        return new_schedules, 0

    def validate_schedule_feasibility(
        self,
        profile: BatteryProfile,
        schedules: list[DispatchSchedule],
    ) -> list[str]:
        issues: list[str] = []
        simulated_soc = profile.state_of_charge_pct
        sim_profile = BatteryProfile(
            nameplate_capacity_mwh=profile.nameplate_capacity_mwh,
            usable_capacity_mwh=profile.usable_capacity_mwh,
            max_charge_mw=profile.max_charge_mw,
            max_discharge_mw=profile.max_discharge_mw,
            state_of_charge_pct=simulated_soc,
            degradation_pct=profile.degradation_pct,
            round_trip_efficiency=profile.round_trip_efficiency,
            cycle_count=profile.cycle_count,
        )
        for i, sched in enumerate(schedules):
            is_charging = sched.action == "charge"
            try:
                new_soc = self._engine.compute_soc_after_dispatch(
                    sim_profile, sched.power_mw, sched.duration_minutes, is_charging=is_charging
                )
                sim_profile = BatteryProfile(
                    nameplate_capacity_mwh=sim_profile.nameplate_capacity_mwh,
                    usable_capacity_mwh=sim_profile.usable_capacity_mwh,
                    max_charge_mw=sim_profile.max_charge_mw,
                    max_discharge_mw=sim_profile.max_discharge_mw,
                    state_of_charge_pct=new_soc,
                    degradation_pct=sim_profile.degradation_pct,
                    round_trip_efficiency=sim_profile.round_trip_efficiency,
                    cycle_count=sim_profile.cycle_count,
                )
            except ValidationError as exc:
                issues.append(f"Schedule {i}: {exc.message}")
            if sched.power_mw > profile.max_discharge_mw and not is_charging:
                issues.append(f"Schedule {i}: power exceeds max discharge")
            if sched.power_mw > profile.max_charge_mw and is_charging:
                issues.append(f"Schedule {i}: power exceeds max charge")
        return issues

    def compute_cycle_impact(
        self, profile: BatteryProfile, schedules: list[DispatchSchedule]
    ) -> dict[str, Any]:
        total_discharge = sum(
            s.power_mw * Decimal(str(s.duration_minutes)) / Decimal("60")
            for s in schedules if s.action in ("discharge", "emergency_discharge")
        )
        dod = total_discharge / profile.usable_capacity_mwh if profile.usable_capacity_mwh else Decimal("0")
        degradation = self._engine.compute_degradation(dod)
        return {
            "total_discharge_mwh": float(total_discharge),
            "depth_of_discharge_pct": float(dod),
            "estimated_degradation_pct": float(degradation),
            "cycles_equivalent": float(dod),
        }
