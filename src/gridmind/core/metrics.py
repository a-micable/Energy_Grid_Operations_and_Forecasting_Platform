from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """In-process metrics collection for operational monitoring."""

    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._points: list[MetricPoint] = []

    def increment(self, name: str, value: float = 1.0, **tags: str) -> None:
        key = self._tagged_key(name, tags)
        self._counters[key] += value
        self._points.append(MetricPoint(name, value, tags=tags))

    def gauge(self, name: str, value: float, **tags: str) -> None:
        key = self._tagged_key(name, tags)
        self._gauges[key] = value
        self._points.append(MetricPoint(name, value, tags=tags))

    def histogram(self, name: str, value: float, **tags: str) -> None:
        key = self._tagged_key(name, tags)
        self._histograms[key].append(value)

    def _tagged_key(self, name: str, tags: dict[str, str]) -> str:
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"

    def get_counter(self, name: str, **tags: str) -> float:
        return self._counters.get(self._tagged_key(name, tags), 0.0)

    def get_gauge(self, name: str, **tags: str) -> float | None:
        return self._gauges.get(self._tagged_key(name, tags))

    def get_histogram_stats(self, name: str, **tags: str) -> dict[str, float]:
        values = self._histograms.get(self._tagged_key(name, tags), [])
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p95": 0}
        sorted_vals = sorted(values)
        p95_idx = int(len(sorted_vals) * 0.95)
        return {
            "count": len(values),
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(values) / len(values),
            "p95": sorted_vals[min(p95_idx, len(sorted_vals) - 1)],
        }

    def export_prometheus(self) -> str:
        lines: list[str] = []
        for key, value in self._counters.items():
            lines.append(f"# TYPE {key.split('[')[0]} counter")
            lines.append(f"{key} {value}")
        for key, value in self._gauges.items():
            lines.append(f"# TYPE {key.split('[')[0]} gauge")
            lines.append(f"{key} {value}")
        return "\n".join(lines)

    def reset(self) -> None:
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._points.clear()


# Global metrics instance
metrics = MetricsCollector()
