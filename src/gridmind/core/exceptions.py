from __future__ import annotations

from typing import Any
from uuid import UUID


class GridMindError(Exception):
    """Base exception for all GridMind errors."""

    code: str = "GRIDMIND_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(GridMindError):
    code = "NOT_FOUND"


class ConflictError(GridMindError):
    code = "CONFLICT"


class ValidationError(GridMindError):
    code = "VALIDATION_ERROR"


class StateTransitionError(GridMindError):
    code = "STATE_TRANSITION_ERROR"

    def __init__(
        self,
        entity_type: str,
        entity_id: UUID,
        current_state: str,
        target_state: str,
        *,
        reason: str | None = None,
    ) -> None:
        message = (
            f"Invalid state transition for {entity_type} {entity_id}: "
            f"{current_state} -> {target_state}"
        )
        if reason:
            message += f" ({reason})"
        super().__init__(message)
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.current_state = current_state
        self.target_state = target_state


class ForecastDriftError(GridMindError):
    code = "FORECAST_DRIFT"

    def __init__(self, forecast_id: UUID, revision_delta_pct: float) -> None:
        super().__init__(
            f"Forecast {forecast_id} revision exceeds drift threshold: {revision_delta_pct:.2%}",
            details={"forecast_id": str(forecast_id), "revision_delta_pct": revision_delta_pct},
        )


class DispatchConflictError(GridMindError):
    code = "DISPATCH_CONFLICT"


class SchedulingConflictError(GridMindError):
    code = "SCHEDULING_CONFLICT"


class CacheInvalidationError(GridMindError):
    code = "CACHE_INVALIDATION_ERROR"


class OptimizationError(GridMindError):
    code = "OPTIMIZATION_ERROR"


class EventOrderingError(GridMindError):
    code = "EVENT_ORDERING_ERROR"


class DependencyGraphError(GridMindError):
    code = "DEPENDENCY_GRAPH_ERROR"


class WorkflowCorruptionError(GridMindError):
    code = "WORKFLOW_CORRUPTION"
