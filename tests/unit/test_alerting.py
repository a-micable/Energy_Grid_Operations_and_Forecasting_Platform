from __future__ import annotations

import pytest

from gridmind.notifications.alerting import AlertChannel, AlertManager, AlertSeverity, AlertStatus


class TestAlertManager:
    def setup_method(self) -> None:
        self.manager = AlertManager()

    def test_frequency_alert_fires(self) -> None:
        alerts = self.manager.evaluate("balancing", {"frequency_hz": 49.85})
        assert len(alerts) >= 1
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_no_alert_for_normal_frequency(self) -> None:
        alerts = self.manager.evaluate("balancing", {"frequency_hz": 50.01})
        freq_alerts = [a for a in alerts if a.rule_id == "ALT-FREQ-001"]
        assert len(freq_alerts) == 0

    def test_cooldown_prevents_duplicate(self) -> None:
        ctx = {"frequency_hz": 49.80}
        first = self.manager.evaluate("balancing", ctx)
        second = self.manager.evaluate("balancing", ctx)
        assert len(first) >= 1
        assert len(second) == 0

    def test_acknowledge_alert(self) -> None:
        alerts = self.manager.evaluate("balancing", {"frequency_hz": 49.85})
        alert = alerts[0]
        acked = self.manager.acknowledge(alert.alert_id, "operator@grid.com")
        assert acked is not None
        assert acked.status == AlertStatus.ACKNOWLEDGED

    def test_resolve_alert(self) -> None:
        alerts = self.manager.evaluate("balancing", {"frequency_hz": 49.85})
        resolved = self.manager.resolve(alerts[0].alert_id)
        assert resolved is not None
        assert resolved.status == AlertStatus.RESOLVED

    def test_get_active_alerts(self) -> None:
        self.manager.evaluate("balancing", {"frequency_hz": 49.85})
        active = self.manager.get_active_alerts(AlertSeverity.CRITICAL)
        assert len(active) >= 1

    @pytest.mark.asyncio
    async def test_notify_with_handler(self) -> None:
        notified: list = []
        async def handler(alert):
            notified.append(alert.alert_id)
        self.manager.register_handler(AlertChannel.DASHBOARD, handler)
        alerts = self.manager.evaluate("balancing", {"frequency_hz": 49.85})
        await self.manager.notify(alerts[0])
        assert len(notified) == 1

    def test_statistics(self) -> None:
        self.manager.evaluate("balancing", {"frequency_hz": 49.85})
        stats = self.manager.get_statistics()
        assert stats["total_alerts"] >= 1
        assert stats["active"] >= 1
