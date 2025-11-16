from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    PAGER = "pager"
    WEBHOOK = "webhook"
    DASHBOARD = "dashboard"


class AlertStatus(StrEnum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class AlertRule:
    rule_id: str
    name: str
    description: str
    severity: AlertSeverity
    condition: str
    channels: list[AlertChannel]
    cooldown_minutes: int = 15
    enabled: bool = True
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    alert_id: UUID
    rule_id: str
    severity: AlertSeverity
    title: str
    message: str
    source: str
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    context: dict[str, Any] = field(default_factory=dict)
    channels_notified: list[AlertChannel] = field(default_factory=list)


AlertHandler = Callable[[Alert], Coroutine[Any, Any, None]]


class AlertManager:
    """Central alert management for grid operational events."""

    def __init__(self) -> None:
        self._rules: dict[str, AlertRule] = {}
        self._alerts: dict[UUID, Alert] = {}
        self._handlers: dict[AlertChannel, AlertHandler] = {}
        self._last_fired: dict[str, datetime] = {}
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        defaults = [
            AlertRule("ALT-FREQ-001", "Frequency Deviation", "Grid frequency outside deadband",
                      AlertSeverity.CRITICAL, "frequency_deviation", [AlertChannel.PAGER, AlertChannel.DASHBOARD], 5),
            AlertRule("ALT-RESV-001", "Reserve Inadequate", "Reserve margin below minimum",
                      AlertSeverity.ERROR, "reserve_inadequate", [AlertChannel.EMAIL, AlertChannel.DASHBOARD], 30),
            AlertRule("ALT-FCST-001", "Forecast Drift", "Forecast revision exceeds drift threshold",
                      AlertSeverity.WARNING, "forecast_drift", [AlertChannel.EMAIL, AlertChannel.DASHBOARD], 60),
            AlertRule("ALT-DISP-001", "Dispatch Conflict", "Conflicting dispatch instructions detected",
                      AlertSeverity.ERROR, "dispatch_conflict", [AlertChannel.DASHBOARD], 10),
            AlertRule("ALT-OUT-001", "Outage Overrun", "Outage duration exceeds planned window",
                      AlertSeverity.WARNING, "outage_overrun", [AlertChannel.EMAIL], 60),
            AlertRule("ALT-BESS-001", "Battery SOC Low", "Battery state of charge below minimum",
                      AlertSeverity.WARNING, "battery_soc_low", [AlertChannel.DASHBOARD], 15),
            AlertRule("ALT-EVT-001", "Event Processing Failure", "Event processing dead letter threshold exceeded",
                      AlertSeverity.ERROR, "event_dlq_threshold", [AlertChannel.EMAIL, AlertChannel.WEBHOOK], 30),
            AlertRule("ALT-COMP-001", "Compliance Violation", "Regulatory compliance rule violated",
                      AlertSeverity.CRITICAL, "compliance_violation", [AlertChannel.EMAIL, AlertChannel.PAGER], 0),
        ]
        for rule in defaults:
            self._rules[rule.rule_id] = rule

    def register_handler(self, channel: AlertChannel, handler: AlertHandler) -> None:
        self._handlers[channel] = handler

    def add_rule(self, rule: AlertRule) -> None:
        self._rules[rule.rule_id] = rule

    def evaluate(self, event_type: str, context: dict[str, Any]) -> list[Alert]:
        fired: list[Alert] = []
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if not self._matches_condition(rule.condition, context):
                continue
            if not self._check_cooldown(rule):
                continue
            alert = Alert(
                alert_id=uuid4(),
                rule_id=rule.rule_id,
                severity=rule.severity,
                title=rule.name,
                message=self._format_message(rule, context),
                source=event_type,
                context=context,
            )
            self._alerts[alert.alert_id] = alert
            self._last_fired[rule.rule_id] = datetime.now(timezone.utc)
            fired.append(alert)
            logger.warning("alert_fired", rule=rule.rule_id, severity=rule.severity.value)
        return fired

    def _matches_condition(self, condition: str, context: dict[str, Any]) -> bool:
        if condition == "frequency_deviation":
            freq = context.get("frequency_hz", 50.0)
            return abs(freq - 50.0) > 0.1
        if condition == "reserve_inadequate":
            reserve = context.get("reserve_mw", 0)
            peak = context.get("peak_demand_mw", 1)
            return reserve / peak < 0.10 if peak else False
        if condition == "forecast_drift":
            return context.get("forecast_drift_pct", 0) > 0.15
        if condition == "dispatch_conflict":
            return context.get("dispatch_conflict_count", 0) > 0
        if condition == "outage_overrun":
            return context.get("outage_overrun_hours", 0) > 0
        if condition == "battery_soc_low":
            return context.get("battery_soc_pct", 1.0) < 0.15
        if condition == "event_dlq_threshold":
            return context.get("dead_letter_count", 0) > 10
        if condition == "compliance_violation":
            return context.get("compliance_violation_count", 0) > 0
        return False

    def _check_cooldown(self, rule: AlertRule) -> bool:
        last = self._last_fired.get(rule.rule_id)
        if not last:
            return True
        elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 60
        return elapsed >= rule.cooldown_minutes

    def _format_message(self, rule: AlertRule, context: dict[str, Any]) -> str:
        parts = [rule.description]
        for key, value in context.items():
            if key in ("frequency_hz", "reserve_mw", "forecast_drift_pct", "battery_soc_pct"):
                parts.append(f"{key}={value}")
        return " | ".join(parts)

    async def notify(self, alert: Alert) -> None:
        rule = self._rules.get(alert.rule_id)
        if not rule:
            return
        for channel in rule.channels:
            handler = self._handlers.get(channel)
            if handler:
                try:
                    await handler(alert)
                    alert.channels_notified.append(channel)
                except Exception as exc:
                    logger.error("alert_notification_failed", channel=channel.value, error=str(exc))

    async def evaluate_and_notify(self, event_type: str, context: dict[str, Any]) -> list[Alert]:
        alerts = self.evaluate(event_type, context)
        for alert in alerts:
            await self.notify(alert)
        return alerts

    def acknowledge(self, alert_id: UUID, actor: str) -> Alert | None:
        alert = self._alerts.get(alert_id)
        if not alert or alert.status != AlertStatus.ACTIVE:
            return None
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = actor
        return alert

    def resolve(self, alert_id: UUID) -> Alert | None:
        alert = self._alerts.get(alert_id)
        if not alert:
            return None
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)
        return alert

    def get_active_alerts(self, severity: AlertSeverity | None = None) -> list[Alert]:
        alerts = [a for a in self._alerts.values() if a.status == AlertStatus.ACTIVE]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    def get_alert_history(
        self, *, limit: int = 100, rule_id: str | None = None
    ) -> list[Alert]:
        alerts = list(self._alerts.values())
        if rule_id:
            alerts = [a for a in alerts if a.rule_id == rule_id]
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)[:limit]

    def suppress_rule(self, rule_id: str, duration_minutes: int = 60) -> None:
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = False
            logger.info("alert_rule_suppressed", rule=rule_id, duration=duration_minutes)

    def enable_rule(self, rule_id: str) -> None:
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = True

    def get_statistics(self) -> dict[str, Any]:
        all_alerts = list(self._alerts.values())
        return {
            "total_alerts": len(all_alerts),
            "active": sum(1 for a in all_alerts if a.status == AlertStatus.ACTIVE),
            "acknowledged": sum(1 for a in all_alerts if a.status == AlertStatus.ACKNOWLEDGED),
            "resolved": sum(1 for a in all_alerts if a.status == AlertStatus.RESOLVED),
            "by_severity": {
                s.value: sum(1 for a in all_alerts if a.severity == s)
                for s in AlertSeverity
            },
            "rules_count": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
        }
