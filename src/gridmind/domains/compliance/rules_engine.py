from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable


class RuleSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    VIOLATION = "violation"
    CRITICAL = "critical"


@dataclass
class ComplianceRule:
    rule_id: str
    name: str
    description: str
    category: str
    severity: RuleSeverity
    evaluator: Callable[[dict[str, Any]], bool]
    remediation: str = ""


@dataclass
class RuleEvaluationResult:
    rule_id: str
    rule_name: str
    passed: bool
    severity: RuleSeverity
    message: str
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    context: dict[str, Any] = field(default_factory=dict)


class ComplianceRulesEngine:
    """Evaluate operational data against regulatory and internal compliance rules."""

    RESERVE_MARGIN_MINIMUM = 0.10
    MAX_MANUAL_OVERRIDES_PER_DAY = 10
    FORECAST_DRIFT_MAX_PCT = 0.20
    MAX_DISPATCH_EMISSIONS_KG = 500000

    def __init__(self) -> None:
        self._rules: list[ComplianceRule] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        self._rules = [
            ComplianceRule(
                rule_id="RES-001",
                name="Minimum Reserve Margin",
                description="Reserve capacity must exceed 10% of peak demand",
                category="reserve",
                severity=RuleSeverity.VIOLATION,
                evaluator=self._check_reserve_margin,
                remediation="Increase reserve commitment or reduce scheduled outages",
            ),
            ComplianceRule(
                rule_id="FCST-001",
                name="Forecast Drift Limit",
                description="Forecast revisions must not exceed 20% delta",
                category="forecasting",
                severity=RuleSeverity.WARNING,
                evaluator=self._check_forecast_drift,
                remediation="Review forecast model and document revision justification",
            ),
            ComplianceRule(
                rule_id="DISP-001",
                name="Emission Limit",
                description="Daily dispatch emissions must not exceed regulatory limit",
                category="dispatch",
                severity=RuleSeverity.VIOLATION,
                evaluator=self._check_emission_limit,
                remediation="Increase renewable dispatch or purchase emission credits",
            ),
            ComplianceRule(
                rule_id="AUD-001",
                name="Manual Override Limit",
                description="Manual overrides must not exceed daily threshold",
                category="audit",
                severity=RuleSeverity.WARNING,
                evaluator=self._check_manual_overrides,
                remediation="Review override authorization procedures",
            ),
            ComplianceRule(
                rule_id="OUT-001",
                name="Outage Approval Required",
                description="Planned outages must be approved before execution",
                category="outage",
                severity=RuleSeverity.VIOLATION,
                evaluator=self._check_outage_approval,
                remediation="Obtain required approvals before proceeding",
            ),
            ComplianceRule(
                rule_id="BAL-001",
                name="Frequency Deviation Limit",
                description="Grid frequency must remain within deadband",
                category="balancing",
                severity=RuleSeverity.CRITICAL,
                evaluator=self._check_frequency_deviation,
                remediation="Initiate emergency balancing procedures",
            ),
        ]

    def _check_reserve_margin(self, ctx: dict) -> bool:
        reserve = ctx.get("reserve_mw", 0)
        peak_demand = ctx.get("peak_demand_mw", 1)
        return reserve / peak_demand >= self.RESERVE_MARGIN_MINIMUM if peak_demand else True

    def _check_forecast_drift(self, ctx: dict) -> bool:
        drift_pct = ctx.get("forecast_drift_pct", 0)
        return drift_pct <= self.FORECAST_DRIFT_MAX_PCT

    def _check_emission_limit(self, ctx: dict) -> bool:
        emissions = ctx.get("total_emissions_kg", 0)
        return emissions <= self.MAX_DISPATCH_EMISSIONS_KG

    def _check_manual_overrides(self, ctx: dict) -> bool:
        count = ctx.get("manual_override_count", 0)
        return count <= self.MAX_MANUAL_OVERRIDES_PER_DAY

    def _check_outage_approval(self, ctx: dict) -> bool:
        status = ctx.get("outage_status", "")
        if status in ("in_progress", "completed"):
            return ctx.get("approved_by") is not None
        return True

    def _check_frequency_deviation(self, ctx: dict) -> bool:
        frequency = ctx.get("frequency_hz", 50.0)
        return abs(frequency - 50.0) <= 0.2

    def evaluate_all(self, context: dict[str, Any]) -> list[RuleEvaluationResult]:
        results: list[RuleEvaluationResult] = []
        for rule in self._rules:
            try:
                passed = rule.evaluator(context)
                results.append(RuleEvaluationResult(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    passed=passed,
                    severity=rule.severity if not passed else RuleSeverity.INFO,
                    message=rule.description if not passed else "Compliant",
                    context={"category": rule.category, "remediation": rule.remediation if not passed else ""},
                ))
            except Exception as exc:
                results.append(RuleEvaluationResult(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    passed=False,
                    severity=RuleSeverity.CRITICAL,
                    message=f"Rule evaluation failed: {exc}",
                ))
        return results

    def get_violations(self, results: list[RuleEvaluationResult]) -> list[RuleEvaluationResult]:
        return [r for r in results if not r.passed and r.severity in (
            RuleSeverity.VIOLATION, RuleSeverity.CRITICAL
        )]

    def add_rule(self, rule: ComplianceRule) -> None:
        self._rules.append(rule)
