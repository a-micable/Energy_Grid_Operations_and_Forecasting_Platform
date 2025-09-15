from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import structlog

from gridmind.domains.balancing.engine import BalancingEngine, BalancingState
from gridmind.domains.battery.engine import BatteryOptimizationEngine, BatteryProfile
from gridmind.domains.dispatch.optimizer import DispatchOptimizer, ResourceOffer
from gridmind.domains.forecasting.engine import ForecastEngine
from gridmind.domains.optimization.engine import MultiStageOptimizer, OptimizationStage
from gridmind.domains.scheduling.engine import ScheduleSlot, SchedulingEngine

logger = structlog.get_logger(__name__)


class ScenarioType(StrEnum):
    NORMAL = "normal"
    PEAK_DEMAND = "peak_demand"
    RENEWABLE_SHORTFALL = "renewable_shortfall"
    EQUIPMENT_FAILURE = "equipment_failure"
    EXTREME_WEATHER = "extreme_weather"
    MARKET_SPIKE = "market_spike"


@dataclass
class SimulationConfig:
    scenario_type: ScenarioType
    zone_id: UUID
    duration_hours: int = 24
    time_step_minutes: int = 60
    base_demand_mw: float = 2000.0
    renewable_capacity_mw: float = 500.0
    thermal_capacity_mw: float = 1500.0
    battery_capacity_mwh: float = 200.0
    seed: int | None = None


@dataclass
class SimulationStep:
    timestamp: datetime
    demand_mw: Decimal
    supply_mw: Decimal
    renewable_output_mw: Decimal
    thermal_output_mw: Decimal
    battery_output_mw: Decimal
    imbalance_mw: Decimal
    frequency_hz: Decimal
    reserve_mw: Decimal
    total_cost: Decimal
    total_emissions_kg: Decimal
    events: list[str] = field(default_factory=list)


@dataclass
class SimulationResult:
    simulation_id: UUID
    config: SimulationConfig
    steps: list[SimulationStep]
    summary: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


class ScenarioSimulator:
    """Run what-if operational scenarios across all GridMind domains."""

    def __init__(self) -> None:
        self._forecast_engine = ForecastEngine()
        self._balancing_engine = BalancingEngine()
        self._dispatch_optimizer = DispatchOptimizer()
        self._battery_engine = BatteryOptimizationEngine()
        self._scheduling_engine = SchedulingEngine()
        self._optimization_engine = MultiStageOptimizer()

    def _apply_scenario_modifiers(
        self, config: SimulationConfig, hour: int
    ) -> dict[str, float]:
        modifiers = {
            "demand_factor": 1.0,
            "renewable_factor": 1.0,
            "thermal_availability": 1.0,
            "reserve_factor": 1.0,
        }
        if config.scenario_type == ScenarioType.PEAK_DEMAND:
            modifiers["demand_factor"] = 1.25 if 17 <= hour <= 21 else 1.1
            modifiers["reserve_factor"] = 0.8
        elif config.scenario_type == ScenarioType.RENEWABLE_SHORTFALL:
            modifiers["renewable_factor"] = 0.3
            modifiers["demand_factor"] = 1.05
        elif config.scenario_type == ScenarioType.EQUIPMENT_FAILURE:
            modifiers["thermal_availability"] = 0.6
            modifiers["reserve_factor"] = 0.5
        elif config.scenario_type == ScenarioType.EXTREME_WEATHER:
            modifiers["demand_factor"] = 1.4 if hour < 8 or hour > 18 else 1.2
            modifiers["renewable_factor"] = 0.1
        elif config.scenario_type == ScenarioType.MARKET_SPIKE:
            modifiers["demand_factor"] = 1.15
        return modifiers

    def run(self, config: SimulationConfig) -> SimulationResult:
        simulation_id = uuid4()
        start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        steps: list[SimulationStep] = []
        warnings: list[str] = []
        total_cost = Decimal("0")
        total_emissions = Decimal("0")
        max_imbalance = Decimal("0")
        reserve_violations = 0

        battery_profile = BatteryProfile(
            nameplate_capacity_mwh=Decimal(str(config.battery_capacity_mwh)),
            usable_capacity_mwh=Decimal(str(config.battery_capacity_mwh * 0.9)),
            max_charge_mw=Decimal("50"),
            max_discharge_mw=Decimal("50"),
            state_of_charge_pct=Decimal("0.50"),
            degradation_pct=Decimal("1.0"),
            round_trip_efficiency=Decimal("0.92"),
            cycle_count=50,
        )

        num_steps = config.duration_hours * 60 // config.time_step_minutes
        for step_idx in range(num_steps):
            ts = start + timedelta(minutes=step_idx * config.time_step_minutes)
            hour = ts.hour
            modifiers = self._apply_scenario_modifiers(config, hour)

            demand = Decimal(str(round(
                config.base_demand_mw * modifiers["demand_factor"], 2
            )))
            renewable = Decimal(str(round(
                config.renewable_capacity_mw * modifiers["renewable_factor"], 2
            )))
            thermal_available = Decimal(str(round(
                config.thermal_capacity_mw * modifiers["thermal_availability"], 2
            )))

            remaining_demand = demand - renewable
            events: list[str] = []

            if remaining_demand > 0:
                resources = [
                    ResourceOffer(
                        resource_id=uuid4(), resource_type="gas_plant",
                        min_output_mw=Decimal("50"),
                        max_output_mw=thermal_available,
                        marginal_cost=Decimal("45"),
                        emission_rate=Decimal("400"),
                        dispatch_priority=60,
                        ramp_rate_mw_per_min=Decimal("10"),
                    ),
                ]
                dispatch_result = self._dispatch_optimizer.optimize(
                    remaining_demand, resources, ts, ts + timedelta(hours=1)
                )
                thermal_output = dispatch_result.total_output_mw
                step_cost = dispatch_result.total_cost
                step_emissions = dispatch_result.total_emissions_kg
                if dispatch_result.unmet_demand_mw > 0:
                    events.append(f"unmet_demand:{dispatch_result.unmet_demand_mw}")
                    warnings.append(f"Unmet demand at {ts}: {dispatch_result.unmet_demand_mw} MW")
            else:
                thermal_output = Decimal("0")
                step_cost = Decimal("0")
                step_emissions = Decimal("0")

            remaining_after_thermal = max(Decimal("0"), demand - renewable - thermal_output)
            battery_output = Decimal("0")
            if remaining_after_thermal > 0 and battery_profile.available_energy_mwh > 0:
                discharge = min(
                    remaining_after_thermal,
                    battery_profile.max_discharge_mw,
                    battery_profile.available_energy_mwh,
                )
                battery_output = discharge
                battery_profile = BatteryProfile(
                    nameplate_capacity_mwh=battery_profile.nameplate_capacity_mwh,
                    usable_capacity_mwh=battery_profile.usable_capacity_mwh,
                    max_charge_mw=battery_profile.max_charge_mw,
                    max_discharge_mw=battery_profile.max_discharge_mw,
                    state_of_charge_pct=self._battery_engine.compute_soc_after_dispatch(
                        battery_profile, discharge, config.time_step_minutes, is_charging=False
                    ),
                    degradation_pct=battery_profile.degradation_pct,
                    round_trip_efficiency=battery_profile.round_trip_efficiency,
                    cycle_count=battery_profile.cycle_count,
                )

            supply = renewable + thermal_output + battery_output
            reserve = Decimal(str(config.thermal_capacity_mw * 0.15 * modifiers["reserve_factor"]))
            state = self._balancing_engine.compute_state(supply, demand, reserve)
            imbalance = state.net_imbalance_mw

            if abs(imbalance) > max_imbalance:
                max_imbalance = abs(imbalance)
            if state.needs_intervention:
                events.append("balancing_intervention_required")
            if reserve < self._balancing_engine.compute_required_reserve(demand):
                reserve_violations += 1
                events.append("reserve_inadequate")

            total_cost += step_cost
            total_emissions += step_emissions

            steps.append(SimulationStep(
                timestamp=ts,
                demand_mw=demand,
                supply_mw=supply,
                renewable_output_mw=renewable,
                thermal_output_mw=thermal_output,
                battery_output_mw=battery_output,
                imbalance_mw=imbalance,
                frequency_hz=state.frequency_hz,
                reserve_mw=reserve,
                total_cost=step_cost,
                total_emissions_kg=step_emissions,
                events=events,
            ))

        summary = {
            "total_steps": len(steps),
            "total_cost": float(total_cost),
            "total_emissions_kg": float(total_emissions),
            "max_imbalance_mw": float(max_imbalance),
            "reserve_violations": reserve_violations,
            "avg_demand_mw": float(sum(s.demand_mw for s in steps) / len(steps)) if steps else 0,
            "avg_renewable_pct": float(
                sum(float(s.renewable_output_mw / s.demand_mw) for s in steps if s.demand_mw) / len(steps)
            ) if steps else 0,
            "intervention_count": sum(1 for s in steps if "balancing_intervention_required" in s.events),
        }

        return SimulationResult(
            simulation_id=simulation_id,
            config=config,
            steps=steps,
            summary=summary,
            warnings=warnings,
        )

    def compare_scenarios(
        self, base_config: SimulationConfig, scenario_types: list[ScenarioType]
    ) -> dict[ScenarioType, SimulationResult]:
        results: dict[ScenarioType, SimulationResult] = {}
        for stype in scenario_types:
            config = SimulationConfig(
                scenario_type=stype,
                zone_id=base_config.zone_id,
                duration_hours=base_config.duration_hours,
                base_demand_mw=base_config.base_demand_mw,
                renewable_capacity_mw=base_config.renewable_capacity_mw,
                thermal_capacity_mw=base_config.thermal_capacity_mw,
                battery_capacity_mwh=base_config.battery_capacity_mwh,
                seed=base_config.seed,
            )
            results[stype] = self.run(config)
        return results

    def run_optimization_pipeline(
        self, config: SimulationConfig
    ) -> dict[str, Any]:
        stages = [
            OptimizationStage(stage_name="cost", objective="minimize_cost"),
            OptimizationStage(stage_name="renewable", objective="maximize_renewable"),
            OptimizationStage(stage_name="reserve", objective="balance_reserve"),
        ]
        data = {
            "demand_mw": config.base_demand_mw,
            "available_reserve_mw": config.thermal_capacity_mw * 0.15,
            "reserve_margin_pct": 0.15,
            "resources": [
                {"id": "thermal", "max_output_mw": config.thermal_capacity_mw, "marginal_cost": 45, "is_renewable": False},
                {"id": "solar", "max_output_mw": config.renewable_capacity_mw * 0.5, "is_renewable": True},
                {"id": "wind", "max_output_mw": config.renewable_capacity_mw * 0.5, "is_renewable": True},
            ],
        }
        return self._optimization_engine.run_multi_stage(stages, data)
