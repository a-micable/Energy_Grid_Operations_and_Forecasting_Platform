from __future__ import annotations

from gridmind.domains.compliance.rules_engine import ComplianceRulesEngine, RuleSeverity


class TestComplianceRulesEngine:
    def setup_method(self) -> None:
        self.engine = ComplianceRulesEngine()

    def test_all_rules_pass_compliant_context(self) -> None:
        ctx = {
            "reserve_mw": 500,
            "peak_demand_mw": 3000,
            "forecast_drift_pct": 0.05,
            "total_emissions_kg": 100000,
            "manual_override_count": 2,
            "frequency_hz": 50.0,
        }
        results = self.engine.evaluate_all(ctx)
        assert all(r.passed for r in results)

    def test_reserve_violation_detected(self) -> None:
        ctx = {"reserve_mw": 100, "peak_demand_mw": 3000}
        results = self.engine.evaluate_all(ctx)
        violations = self.engine.get_violations(results)
        assert any(v.rule_id == "RES-001" for v in violations)

    def test_frequency_critical_violation(self) -> None:
        ctx = {"frequency_hz": 49.5}
        results = self.engine.evaluate_all(ctx)
        freq_result = next(r for r in results if r.rule_id == "BAL-001")
        assert not freq_result.passed
        assert freq_result.severity == RuleSeverity.CRITICAL

    def test_emission_violation(self) -> None:
        ctx = {"total_emissions_kg": 600000}
        results = self.engine.evaluate_all(ctx)
        violations = self.engine.get_violations(results)
        assert any(v.rule_id == "DISP-001" for v in violations)

    def test_outage_approval_required(self) -> None:
        ctx = {"outage_status": "in_progress", "approved_by": None}
        results = self.engine.evaluate_all(ctx)
        out_result = next(r for r in results if r.rule_id == "OUT-001")
        assert not out_result.passed
