from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from gridmind.core.exceptions import StateTransitionError

S = TypeVar("S")
E = TypeVar("E")


class StateMachine(Generic[S, E]):
    """Finite state machine with guarded transitions."""

    def __init__(
        self,
        initial: S,
        transitions: dict[tuple[S, E], S],
        guards: dict[tuple[S, E], Callable[[], bool]] | None = None,
        entity_type: str = "entity",
        entity_id_getter: Callable[[], str] | None = None,
    ) -> None:
        self._state = initial
        self._transitions = transitions
        self._guards = guards or {}
        self._entity_type = entity_type
        self._entity_id_getter = entity_id_getter or (lambda: "unknown")
        self._history: list[tuple[S, E, S]] = []

    @property
    def state(self) -> S:
        return self._state

    @property
    def history(self) -> list[tuple[S, E, S]]:
        return list(self._history)

    def can_transition(self, event: E) -> bool:
        key = (self._state, event)
        if key not in self._transitions:
            return False
        guard = self._guards.get(key)
        return guard() if guard else True

    def transition(self, event: E) -> S:
        key = (self._state, event)
        if key not in self._transitions:
            raise StateTransitionError(
                self._entity_type,
                self._entity_id_getter(),
                str(self._state),
                str(event),
                reason="transition not defined",
            )
        guard = self._guards.get(key)
        if guard and not guard():
            raise StateTransitionError(
                self._entity_type,
                self._entity_id_getter(),
                str(self._state),
                str(event),
                reason="guard rejected transition",
            )
        old = self._state
        new = self._transitions[key]
        self._state = new
        self._history.append((old, event, new))
        return new

    def allowed_events(self) -> list[E]:
        return [e for (s, e) in self._transitions if s == self._state and self.can_transition(e)]
