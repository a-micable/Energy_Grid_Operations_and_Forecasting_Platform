from __future__ import annotations

from datetime import datetime, timezone

from gridmind.domains.audit.reconstructor import HistoricalReconstructor


class TestHistoricalReconstructor:
    def setup_method(self) -> None:
        self.t0 = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
        self.t1 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.t2 = datetime(2025, 1, 2, 0, 0, tzinfo=timezone.utc)
        self.entries = [
            {
                "occurred_at": self.t0,
                "action": "created",
                "actor": "system",
                "before_state": None,
                "after_state": {"status": "draft", "value": 100},
            },
            {
                "occurred_at": self.t1,
                "action": "updated",
                "actor": "operator@grid.com",
                "before_state": {"status": "draft", "value": 100},
                "after_state": {"status": "active", "value": 150},
            },
        ]

    def test_reconstruct_at_time(self) -> None:
        recon = HistoricalReconstructor(self.entries)
        state = recon.reconstruct_at(self.t1)
        assert state == {"status": "active", "value": 150}

    def test_reconstruct_before_first_entry(self) -> None:
        recon = HistoricalReconstructor(self.entries)
        state = recon.reconstruct_at(self.t0)
        assert state == {"status": "draft", "value": 100}

    def test_timeline_generation(self) -> None:
        recon = HistoricalReconstructor(self.entries)
        timeline = recon.build_timeline(self.t0, self.t2)
        assert len(timeline) == 2
        assert timeline[1]["changes"]["status"]["from"] == "draft"

    def test_integrity_check_passes_for_consistent_trail(self) -> None:
        recon = HistoricalReconstructor(self.entries)
        issues = recon.verify_integrity()
        assert len(issues) == 0
