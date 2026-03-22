"""Tests for :class:`~kymflow.gui_v2.controllers.kym_event_controller.KymEventController`."""

from __future__ import annotations

import pytest

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.kym_event_controller import KymEventController
from kymflow.gui_v2.events import SelectionOrigin, SetKymEventRangeState
from kymflow.gui_v2.events_state import BlockingMode, InteractionBlocked
from kymflow.gui_v2.state import AppState


def test_set_kym_event_range_emits_state_then_interaction_blocked_in_order(
    bus: EventBus, app_state: AppState
) -> None:
    """Mirroring range intent emits SetKymEventRangeState(state) then InteractionBlocked(state)."""
    captured: list[object] = []

    def capture(ev: object) -> None:
        captured.append(ev)

    bus.subscribe_state(SetKymEventRangeState, capture)
    bus.subscribe_state(InteractionBlocked, capture)

    KymEventController(app_state, bus)

    bus.emit(
        SetKymEventRangeState(
            enabled=True,
            event_id="ev-1",
            roi_id=1,
            path="/tmp/f.tif",
            origin=SelectionOrigin.EVENT_TABLE,
            phase="intent",
        )
    )

    assert len(captured) == 2
    assert isinstance(captured[0], SetKymEventRangeState)
    assert captured[0].phase == "state"
    assert captured[0].enabled is True
    assert isinstance(captured[1], InteractionBlocked)
    assert captured[1].blocked is True
    assert captured[1].mode == BlockingMode.KYM_EVENT_RANGE
    assert captured[1].phase == "state"


def test_set_kym_event_range_disable_emits_none_mode(bus: EventBus, app_state: AppState) -> None:
    """When range is disabled, InteractionBlocked carries NONE mode and blocked=False."""
    captured_ib: list[InteractionBlocked] = []

    def capture_ib(ev: InteractionBlocked) -> None:
        captured_ib.append(ev)

    bus.subscribe_state(InteractionBlocked, capture_ib)
    bus.subscribe_state(SetKymEventRangeState, lambda _e: None)

    KymEventController(app_state, bus)

    bus.emit(
        SetKymEventRangeState(
            enabled=False,
            event_id=None,
            roi_id=None,
            path=None,
            origin=SelectionOrigin.EVENT_TABLE,
            phase="intent",
        )
    )

    assert len(captured_ib) == 1
    assert captured_ib[0].blocked is False
    assert captured_ib[0].mode == BlockingMode.NONE
