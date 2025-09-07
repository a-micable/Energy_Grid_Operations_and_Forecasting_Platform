from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


class PlaybookSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PlaybookCategory(StrEnum):
    BALANCING = "balancing"
    FORECASTING = "forecasting"
    OUTAGE = "outage"
    DISPATCH = "dispatch"
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"


@dataclass
class PlaybookStep:
    order: int
    action: str
    description: str
    responsible_role: str
    timeout_minutes: int = 30
    automated: bool = False
    preconditions: list[str] = field(default_factory=list)
    verification: str = ""


@dataclass
class OperationalPlaybook:
    playbook_id: str
    name: str
    category: PlaybookCategory
    severity: PlaybookSeverity
    description: str
    trigger_conditions: list[str]
    steps: list[PlaybookStep]
    escalation_path: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


@dataclass
class PlaybookExecution:
    execution_id: UUID
    playbook_id: str
    started_at: datetime
    current_step: int = 0
    status: str = "in_progress"
    completed_steps: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    completed_at: datetime | None = None


class PlaybookRegistry:
    """Registry of operational playbooks for grid events."""

    def __init__(self) -> None:
        self._playbooks: dict[str, OperationalPlaybook] = {}
        self._executions: dict[UUID, PlaybookExecution] = {}
        self._register_standard_playbooks()

    def _register_standard_playbooks(self) -> None:
        self.register(OperationalPlaybook(
            playbook_id="PB-BAL-001",
            name="Grid Frequency Deviation Response",
            category=PlaybookCategory.BALANCING,
            severity=PlaybookSeverity.CRITICAL,
            description="Response procedure for grid frequency outside deadband",
            trigger_conditions=[
                "frequency_hz < 49.95 or frequency_hz > 50.05",
                "net_imbalance_mw > 100",
            ],
            steps=[
                PlaybookStep(1, "assess_state", "Review current balancing snapshot", "shift_operator", 5),
                PlaybookStep(2, "identify_cause", "Identify source of imbalance", "shift_operator", 10),
                PlaybookStep(3, "dispatch_reserves", "Dispatch available reserve capacity", "dispatcher", 15, automated=True),
                PlaybookStep(4, "monitor_frequency", "Monitor frequency recovery", "shift_operator", 30),
                PlaybookStep(5, "document_actions", "Document all actions in audit trail", "shift_operator", 10),
            ],
            escalation_path=["shift_supervisor", "control_center_manager", "grid_operations_director"],
        ))

        self.register(OperationalPlaybook(
            playbook_id="PB-FCST-001",
            name="Forecast Drift Investigation",
            category=PlaybookCategory.FORECASTING,
            severity=PlaybookSeverity.MEDIUM,
            description="Investigate and resolve significant forecast revision drift",
            trigger_conditions=["forecast_drift_pct > 0.15", "revision_count > 3 in 24h"],
            steps=[
                PlaybookStep(1, "compare_actuals", "Compare forecast against SCADA actuals", "forecaster", 20),
                PlaybookStep(2, "identify_driver", "Identify weather/load model divergence", "forecaster", 30),
                PlaybookStep(3, "evaluate_model", "Evaluate model performance metrics", "senior_forecaster", 30),
                PlaybookStep(4, "decide_action", "Decide: accept revision, revert, or recalibrate", "forecast_manager", 15),
                PlaybookStep(5, "update_model", "Apply model parameter updates if needed", "forecaster", 60, automated=True),
            ],
        ))

        self.register(OperationalPlaybook(
            playbook_id="PB-OUT-001",
            name="Emergency Outage Declaration",
            category=PlaybookCategory.EMERGENCY,
            severity=PlaybookSeverity.CRITICAL,
            description="Declare and manage emergency equipment outage",
            trigger_conditions=["equipment_failure_detected", "safety_system_activated"],
            steps=[
                PlaybookStep(1, "secure_equipment", "Secure failed equipment safely", "field_operator", 15),
                PlaybookStep(2, "declare_outage", "Create emergency outage record", "shift_operator", 5, automated=True),
                PlaybookStep(3, "assess_impact", "Calculate grid impact and reserve adequacy", "dispatcher", 10, automated=True),
                PlaybookStep(4, "redispatch", "Execute redispatch optimization", "dispatcher", 20, automated=True),
                PlaybookStep(5, "notify_stakeholders", "Notify market operator and stakeholders", "shift_supervisor", 10),
                PlaybookStep(6, "plan_restoration", "Develop equipment restoration plan", "maintenance_planner", 60),
            ],
            escalation_path=["shift_supervisor", "emergency_response_team"],
        ))

        self.register(OperationalPlaybook(
            playbook_id="PB-DISP-001",
            name="Dispatch Conflict Resolution",
            category=PlaybookCategory.DISPATCH,
            severity=PlaybookSeverity.HIGH,
            description="Resolve conflicting dispatch instructions",
            trigger_conditions=["dispatch_conflict_detected", "overlapping_resource_allocation"],
            steps=[
                PlaybookStep(1, "identify_conflicts", "List all conflicting dispatch instructions", "dispatcher", 10, automated=True),
                PlaybookStep(2, "assess_priority", "Determine priority based on cost and reliability", "dispatcher", 15),
                PlaybookStep(3, "cancel_lower", "Cancel lower priority conflicting instructions", "dispatcher", 10),
                PlaybookStep(4, "reoptimize", "Re-run dispatch optimization", "dispatcher", 20, automated=True),
                PlaybookStep(5, "verify_feasible", "Verify feasible dispatch schedule", "dispatcher", 10, automated=True),
            ],
        ))

        self.register(OperationalPlaybook(
            playbook_id="PB-BESS-001",
            name="Emergency Battery Discharge",
            category=PlaybookCategory.EMERGENCY,
            severity=PlaybookSeverity.CRITICAL,
            description="Execute emergency battery storage discharge",
            trigger_conditions=["reserve_inadequate", "frequency_critical", "load_shed_imminent"],
            steps=[
                PlaybookStep(1, "verify_soc", "Verify battery state of charge adequate", "dispatcher", 5, automated=True),
                PlaybookStep(2, "calculate_need", "Calculate discharge requirement", "dispatcher", 5, automated=True),
                PlaybookStep(3, "authorize", "Obtain emergency discharge authorization", "shift_supervisor", 5),
                PlaybookStep(4, "execute", "Execute emergency discharge schedule", "dispatcher", 5, automated=True),
                PlaybookStep(5, "monitor", "Monitor grid response for 30 minutes", "shift_operator", 30),
            ],
        ))

        self.register(OperationalPlaybook(
            playbook_id="PB-MAINT-001",
            name="Planned Maintenance Window Execution",
            category=PlaybookCategory.MAINTENANCE,
            severity=PlaybookSeverity.LOW,
            description="Execute approved planned maintenance outage",
            trigger_conditions=["outage_status == approved", "maintenance_window_start_reached"],
            steps=[
                PlaybookStep(1, "pre_check", "Verify all dependencies satisfied", "maintenance_planner", 15, automated=True),
                PlaybookStep(2, "ramp_down", "Ramp down affected generation resources", "dispatcher", 30, automated=True),
                PlaybookStep(3, "isolate", "Confirm equipment isolation", "field_operator", 15),
                PlaybookStep(4, "begin_work", "Transition outage to in_progress", "shift_operator", 5, automated=True),
                PlaybookStep(5, "monitor_grid", "Monitor grid stability during maintenance", "shift_operator", 480),
                PlaybookStep(6, "restore", "Restore equipment and ramp up", "dispatcher", 60, automated=True),
                PlaybookStep(7, "complete", "Mark outage completed and verify", "shift_operator", 15, automated=True),
            ],
        ))

    def register(self, playbook: OperationalPlaybook) -> None:
        self._playbooks[playbook.playbook_id] = playbook

    def get(self, playbook_id: str) -> OperationalPlaybook | None:
        return self._playbooks.get(playbook_id)

    def find_by_trigger(self, context: dict[str, Any]) -> list[OperationalPlaybook]:
        matched: list[OperationalPlaybook] = []
        for playbook in self._playbooks.values():
            for condition in playbook.trigger_conditions:
                if self._evaluate_condition(condition, context):
                    matched.append(playbook)
                    break
        return sorted(matched, key=lambda p: p.severity.value, reverse=True)

    def _evaluate_condition(self, condition: str, context: dict[str, Any]) -> bool:
        if "frequency_hz" in condition and "frequency_hz" in context:
            freq = context["frequency_hz"]
            if "< 49.95" in condition and freq < 49.95:
                return True
            if "> 50.05" in condition and freq > 50.05:
                return True
        if "forecast_drift_pct" in condition and "forecast_drift_pct" in context:
            if "> 0.15" in condition and context["forecast_drift_pct"] > 0.15:
                return True
        if "net_imbalance_mw" in condition and "net_imbalance_mw" in context:
            if "> 100" in condition and abs(context["net_imbalance_mw"]) > 100:
                return True
        if condition in context and context[condition]:
            return True
        if "==" in condition:
            parts = condition.split("==")
            key = parts[0].strip()
            val = parts[1].strip().strip('"')
            if key in context and str(context[key]) == val:
                return True
        return False

    def start_execution(self, playbook_id: str) -> PlaybookExecution | None:
        from uuid import uuid4
        playbook = self.get(playbook_id)
        if not playbook:
            return None
        execution = PlaybookExecution(
            execution_id=uuid4(),
            playbook_id=playbook_id,
            started_at=datetime.now(timezone.utc),
        )
        self._executions[execution.execution_id] = execution
        logger.info("playbook_started", playbook=playbook_id, execution=str(execution.execution_id))
        return execution

    def advance_step(self, execution_id: UUID, notes: str = "") -> PlaybookStep | None:
        execution = self._executions.get(execution_id)
        if not execution or execution.status != "in_progress":
            return None
        playbook = self.get(execution.playbook_id)
        if not playbook:
            return None
        if execution.current_step < len(playbook.steps):
            step = playbook.steps[execution.current_step]
            execution.completed_steps.append(execution.current_step)
            execution.current_step += 1
            if notes:
                execution.notes.append(notes)
            if execution.current_step >= len(playbook.steps):
                execution.status = "completed"
                execution.completed_at = datetime.now(timezone.utc)
            return step
        return None

    def get_escalation_contact(self, playbook_id: str, level: int = 0) -> str | None:
        playbook = self.get(playbook_id)
        if not playbook or level >= len(playbook.escalation_path):
            return None
        return playbook.escalation_path[level]

    def list_playbooks(self, category: PlaybookCategory | None = None) -> list[OperationalPlaybook]:
        playbooks = list(self._playbooks.values())
        if category:
            playbooks = [p for p in playbooks if p.category == category]
        return playbooks

    def get_execution_status(self, execution_id: UUID) -> dict[str, Any] | None:
        execution = self._executions.get(execution_id)
        if not execution:
            return None
        playbook = self.get(execution.playbook_id)
        total_steps = len(playbook.steps) if playbook else 0
        return {
            "execution_id": str(execution.execution_id),
            "playbook_id": execution.playbook_id,
            "status": execution.status,
            "progress_pct": len(execution.completed_steps) / total_steps * 100 if total_steps else 0,
            "current_step": execution.current_step,
            "total_steps": total_steps,
            "notes": execution.notes,
        }
