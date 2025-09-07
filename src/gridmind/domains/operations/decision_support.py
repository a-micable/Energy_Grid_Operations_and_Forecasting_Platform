from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from gridmind.domains.operations.playbooks import PlaybookRegistry


@dataclass
class DecisionOption:
    option_id: str
    description: str
    estimated_cost: Decimal
    estimated_risk: str
    estimated_duration_minutes: int
    prerequisites: list[str] = field(default_factory=list)
    impacts: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionRecommendation:
    recommended_option: str
    confidence: float
    reasoning: str
    alternatives: list[DecisionOption]
    triggered_playbooks: list[str]
    warnings: list[str] = field(default_factory=list)


class OperationalDecisionSupport:
    """Decision support system for grid operators."""

    def __init__(self, playbook_registry: PlaybookRegistry | None = None) -> None:
        self._playbooks = playbook_registry or PlaybookRegistry()

    def recommend_balancing_action(
        self,
        imbalance_mw: Decimal,
        available_reserve_mw: Decimal,
        frequency_hz: float,
        battery_soc_pct: float = 0.5,
    ) -> DecisionRecommendation:
        options: list[DecisionOption] = []
        warnings: list[str] = []
        triggered: list[str] = []

        if abs(float(imbalance_mw)) < 10:
            return DecisionRecommendation(
                recommended_option="monitor",
                confidence=0.95,
                reasoning="Imbalance within acceptable deadband",
                alternatives=[],
                triggered_playbooks=[],
            )

        if available_reserve_mw >= abs(imbalance_mw):
            options.append(DecisionOption(
                option_id="dispatch_reserve",
                description="Dispatch available reserve capacity",
                estimated_cost=abs(imbalance_mw) * Decimal("50"),
                estimated_risk="low",
                estimated_duration_minutes=15,
                impacts={"imbalance_reduction_mw": float(abs(imbalance_mw))},
            ))

        if battery_soc_pct > 0.2:
            options.append(DecisionOption(
                option_id="battery_discharge",
                description="Discharge battery storage",
                estimated_cost=abs(imbalance_mw) * Decimal("35"),
                estimated_risk="medium",
                estimated_duration_minutes=10,
                impacts={"soc_reduction_pct": float(abs(imbalance_mw)) / 100},
            ))

        if abs(frequency_hz - 50.0) > 0.1:
            warnings.append("Frequency deviation requires immediate action")
            triggered.extend(p.playbook_id for p in self._playbooks.find_by_trigger({
                "frequency_hz": frequency_hz,
                "net_imbalance_mw": float(imbalance_mw),
            }))

        if abs(float(imbalance_mw)) > 200 and available_reserve_mw < abs(imbalance_mw):
            options.append(DecisionOption(
                option_id="load_shed",
                description="Initiate controlled load shedding",
                estimated_cost=Decimal("0"),
                estimated_risk="high",
                estimated_duration_minutes=5,
                prerequisites=["shift_supervisor_approval"],
                impacts={"customers_affected_estimate": int(abs(imbalance_mw) * 100)},
            ))
            warnings.append("Reserve inadequate for imbalance - load shed may be required")

        if not options:
            return DecisionRecommendation(
                recommended_option="escalate",
                confidence=0.5,
                reasoning="No automated options available",
                alternatives=[],
                triggered_playbooks=triggered,
                warnings=warnings,
            )

        best = min(options, key=lambda o: (o.estimated_risk != "low", o.estimated_cost))
        return DecisionRecommendation(
            recommended_option=best.option_id,
            confidence=0.85 if best.estimated_risk == "low" else 0.65,
            reasoning=f"Lowest cost/risk option for {imbalance_mw} MW imbalance",
            alternatives=options,
            triggered_playbooks=triggered,
            warnings=warnings,
        )

    def recommend_outage_scheduling(
        self,
        proposed_start: datetime,
        proposed_end: datetime,
        impact_mw: float,
        existing_outages: list[dict],
        peak_demand_mw: float,
    ) -> DecisionRecommendation:
        duration_hours = (proposed_end - proposed_start).total_seconds() / 3600
        options: list[DecisionOption] = []
        warnings: list[str] = []

        if impact_mw > peak_demand_mw * 0.2:
            warnings.append("Outage impact exceeds 20% of peak demand")

        overlapping = [
            o for o in existing_outages
            if o.get("planned_start") < proposed_end and o.get("planned_end") > proposed_start
        ]
        if overlapping:
            warnings.append(f"{len(overlapping)} overlapping outages detected")
            options.append(DecisionOption(
                option_id="reschedule",
                description="Reschedule to non-conflicting window",
                estimated_cost=Decimal("5000"),
                estimated_risk="low",
                estimated_duration_minutes=60,
            ))

        options.append(DecisionOption(
            option_id="proceed",
            description="Proceed with proposed schedule",
            estimated_cost=Decimal(str(impact_mw * duration_hours * 50)),
            estimated_risk="medium" if impact_mw > 100 else "low",
            estimated_duration_minutes=int(duration_hours * 60),
        ))

        options.append(DecisionOption(
            option_id="split",
            description="Split into smaller maintenance windows",
            estimated_cost=Decimal(str(impact_mw * duration_hours * 60)),
            estimated_risk="low",
            estimated_duration_minutes=int(duration_hours * 60 * 1.5),
        ))

        best = options[0] if overlapping else options[0]
        if not overlapping:
            best = next(o for o in options if o.option_id == "proceed")

        return DecisionRecommendation(
            recommended_option=best.option_id,
            confidence=0.80 if not warnings else 0.55,
            reasoning="Schedule assessment based on impact and conflicts",
            alternatives=options,
            triggered_playbooks=[],
            warnings=warnings,
        )

    def recommend_dispatch_adjustment(
        self,
        current_output_mw: Decimal,
        target_output_mw: Decimal,
        marginal_cost: Decimal,
        market_price: Decimal,
        ramp_rate_mw_per_min: Decimal,
    ) -> DecisionRecommendation:
        delta = target_output_mw - current_output_mw
        options: list[DecisionOption] = []

        if delta == 0:
            return DecisionRecommendation(
                recommended_option="hold",
                confidence=1.0,
                reasoning="Already at target output",
                alternatives=[],
                triggered_playbooks=[],
            )

        ramp_time = abs(float(delta)) / float(ramp_rate_mw_per_min) if ramp_rate_mw_per_min else 60
        revenue_change = delta * market_price
        cost_change = delta * marginal_cost if delta > 0 else -delta * marginal_cost

        options.append(DecisionOption(
            option_id="adjust_to_target",
            description=f"Adjust output by {delta} MW",
            estimated_cost=abs(cost_change),
            estimated_risk="low",
            estimated_duration_minutes=int(ramp_time),
            impacts={"revenue_change": float(revenue_change)},
        ))

        if market_price > marginal_cost and delta > 0:
            reasoning = "Market price exceeds marginal cost - increase recommended"
            recommended = "adjust_to_target"
            confidence = 0.90
        elif market_price < marginal_cost and delta > 0:
            reasoning = "Market price below marginal cost - hold current output"
            recommended = "hold"
            confidence = 0.75
        else:
            reasoning = "Standard dispatch adjustment"
            recommended = "adjust_to_target"
            confidence = 0.80

        return DecisionRecommendation(
            recommended_option=recommended,
            confidence=confidence,
            reasoning=reasoning,
            alternatives=options,
            triggered_playbooks=[],
        )
