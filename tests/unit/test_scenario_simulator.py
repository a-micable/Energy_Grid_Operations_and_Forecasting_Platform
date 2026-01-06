from __future__ import annotations

from uuid import uuid4

from gridmind.domains.simulation.scenario_runner import (
    ScenarioSimulator,
    ScenarioType,
    SimulationConfig,
)


class TestScenarioSimulator:
    def setup_method(self) -> None:
        self.simulator = ScenarioSimulator()
        self.config = SimulationConfig(
            scenario_type=ScenarioType.NORMAL,
            zone_id=uuid4(),
            duration_hours=24,
            base_demand_mw=2000,
            renewable_capacity_mw=500,
            thermal_capacity_mw=1500,
            seed=42,
        )

    def test_normal_scenario_completes(self) -> None:
        result = self.simulator.run(self.config)
        assert len(result.steps) == 24
        assert result.summary["total_steps"] == 24

    def test_peak_demand_increases_demand(self) -> None:
        peak_config = SimulationConfig(
            scenario_type=ScenarioType.PEAK_DEMAND,
            zone_id=self.config.zone_id,
            duration_hours=24,
            base_demand_mw=2000,
            seed=42,
        )
        normal = self.simulator.run(self.config)
        peak = self.simulator.run(peak_config)
        assert peak.summary["avg_demand_mw"] >= normal.summary["avg_demand_mw"]

    def test_renewable_shortfall_reduces_renewable(self) -> None:
        shortfall_config = SimulationConfig(
            scenario_type=ScenarioType.RENEWABLE_SHORTFALL,
            zone_id=self.config.zone_id,
            duration_hours=24,
            base_demand_mw=2000,
            renewable_capacity_mw=500,
            seed=42,
        )
        result = self.simulator.run(shortfall_config)
        assert result.summary["avg_renewable_pct"] < 0.5

    def test_compare_scenarios(self) -> None:
        results = self.simulator.compare_scenarios(
            self.config,
            [ScenarioType.NORMAL, ScenarioType.PEAK_DEMAND, ScenarioType.EQUIPMENT_FAILURE],
        )
        assert len(results) == 3

    def test_optimization_pipeline(self) -> None:
        result = self.simulator.run_optimization_pipeline(self.config)
        assert "cost" in result["stages"]
        assert "reserve" in result["stages"]
