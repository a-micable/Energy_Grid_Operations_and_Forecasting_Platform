from __future__ import annotations

from gridmind.domains.optimization.engine import MultiStageOptimizer, OptimizationStage


class TestMultiStageOptimizer:
    def setup_method(self) -> None:
        self.optimizer = MultiStageOptimizer()

    def test_minimize_cost_stage(self) -> None:
        stage = OptimizationStage(stage_name="cost", objective="minimize_cost")
        data = {
            "demand_mw": 500,
            "resources": [
                {"id": "r1", "max_output_mw": 200, "marginal_cost": 30},
                {"id": "r2", "max_output_mw": 400, "marginal_cost": 50},
            ],
        }
        result = self.optimizer.run_stage(stage, data)
        assert result["status"] == "optimal"
        assert result["total_cost"] > 0

    def test_maximize_renewable_stage(self) -> None:
        stage = OptimizationStage(stage_name="renewable", objective="maximize_renewable")
        data = {
            "demand_mw": 300,
            "resources": [
                {"id": "s1", "max_output_mw": 200, "is_renewable": True},
                {"id": "g1", "max_output_mw": 500, "is_renewable": False, "marginal_cost": 40},
            ],
        }
        result = self.optimizer.run_stage(stage, data)
        assert result["renewable_pct"] > 0.5

    def test_multi_stage_pipeline(self) -> None:
        stages = [
            OptimizationStage(stage_name="cost", objective="minimize_cost"),
            OptimizationStage(stage_name="reserve", objective="balance_reserve"),
        ]
        data = {
            "demand_mw": 500,
            "available_reserve_mw": 100,
            "reserve_margin_pct": 0.15,
            "resources": [{"id": "r1", "max_output_mw": 600, "marginal_cost": 40}],
        }
        result = self.optimizer.run_multi_stage(stages, data)
        assert "cost" in result["stages"]
        assert "reserve" in result["stages"]

    def test_scenario_simulation_ranks_results(self) -> None:
        stage = OptimizationStage(stage_name="cost", objective="minimize_cost")
        base = {
            "demand_mw": 500,
            "resources": [{"id": "r1", "max_output_mw": 600, "marginal_cost": 40}],
        }
        scenarios = [
            {"name": "high_demand", "parameters": {"demand_mw": 700}},
            {"name": "low_demand", "parameters": {"demand_mw": 300}},
        ]
        results = self.optimizer.simulate_scenarios(base, scenarios, stage)
        assert len(results) == 2
        assert results[0].rank == 1
