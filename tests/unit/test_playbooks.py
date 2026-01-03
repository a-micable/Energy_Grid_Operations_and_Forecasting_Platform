from __future__ import annotations

from uuid import uuid4

from gridmind.domains.operations.playbooks import PlaybookCategory, PlaybookRegistry


class TestPlaybookRegistry:
    def setup_method(self) -> None:
        self.registry = PlaybookRegistry()

    def test_standard_playbooks_registered(self) -> None:
        playbooks = self.registry.list_playbooks()
        assert len(playbooks) >= 6

    def test_find_by_frequency_trigger(self) -> None:
        matched = self.registry.find_by_trigger({"frequency_hz": 49.90})
        assert any(p.playbook_id == "PB-BAL-001" for p in matched)

    def test_find_by_drift_trigger(self) -> None:
        matched = self.registry.find_by_trigger({"forecast_drift_pct": 0.20})
        assert any(p.playbook_id == "PB-FCST-001" for p in matched)

    def test_execution_lifecycle(self) -> None:
        execution = self.registry.start_execution("PB-BAL-001")
        assert execution is not None
        step = self.registry.advance_step(execution.execution_id, "Completed assessment")
        assert step is not None
        status = self.registry.get_execution_status(execution.execution_id)
        assert status is not None
        assert status["current_step"] == 1

    def test_escalation_path(self) -> None:
        contact = self.registry.get_escalation_contact("PB-BAL-001", 0)
        assert contact == "shift_supervisor"

    def test_filter_by_category(self) -> None:
        emergency = self.registry.list_playbooks(PlaybookCategory.EMERGENCY)
        assert all(p.category == PlaybookCategory.EMERGENCY for p in emergency)
