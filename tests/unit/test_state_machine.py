from __future__ import annotations

from enum import StrEnum

import pytest

from gridmind.core.exceptions import StateTransitionError
from gridmind.core.state import StateMachine


class States(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"


class Events(StrEnum):
    START = "start"
    STOP = "stop"


class TestStateMachine:
    def test_valid_transition(self) -> None:
        sm = StateMachine(
            States.IDLE,
            {
                (States.IDLE, Events.START): States.RUNNING,
                (States.RUNNING, Events.STOP): States.STOPPED,
            },
        )
        assert sm.transition(Events.START) == States.RUNNING
        assert sm.transition(Events.STOP) == States.STOPPED

    def test_invalid_transition_raises(self) -> None:
        sm = StateMachine(
            States.IDLE,
            {(States.IDLE, Events.START): States.RUNNING},
        )
        with pytest.raises(StateTransitionError):
            sm.transition(Events.STOP)

    def test_guard_blocks_transition(self) -> None:
        sm = StateMachine(
            States.IDLE,
            {(States.IDLE, Events.START): States.RUNNING},
            guards={(States.IDLE, Events.START): lambda: False},
        )
        with pytest.raises(StateTransitionError):
            sm.transition(Events.START)

    def test_history_tracks_transitions(self) -> None:
        sm = StateMachine(
            States.IDLE,
            {(States.IDLE, Events.START): States.RUNNING},
        )
        sm.transition(Events.START)
        assert len(sm.history) == 1
        assert sm.history[0] == (States.IDLE, Events.START, States.RUNNING)
