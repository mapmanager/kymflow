"""Tests for EventBus per-client isolation and event handling."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from kymflow.gui_v2.bus import BusConfig, EventBus
from kymflow.gui_v2.events import FileSelection, SelectionOrigin


@dataclass(frozen=True)
class BusTestEvent:
    """Test event for bus testing."""

    value: int


def test_bus_subscribe_emit(bus: EventBus) -> None:
    """Test basic subscribe and emit functionality."""
    received: list[BusTestEvent] = []

    def handler(event: BusTestEvent) -> None:
        received.append(event)

    bus.subscribe(BusTestEvent, handler)
    bus.emit(BusTestEvent(value=42))

    assert len(received) == 1
    assert received[0].value == 42


def test_bus_deduplicate_subscriptions(bus: EventBus) -> None:
    """Test that duplicate subscriptions are prevented."""
    call_count = 0

    def handler(_event: BusTestEvent) -> None:
        nonlocal call_count
        call_count += 1

    # Subscribe same handler twice
    bus.subscribe(BusTestEvent, handler)
    bus.subscribe(BusTestEvent, handler)

    # Emit event - should only call handler once
    bus.emit(BusTestEvent(value=1))

    assert call_count == 1


def test_bus_multiple_handlers(bus: EventBus) -> None:
    """Test that multiple handlers receive events."""
    received_1: list[BusTestEvent] = []
    received_2: list[BusTestEvent] = []

    def handler1(event: BusTestEvent) -> None:
        received_1.append(event)

    def handler2(event: BusTestEvent) -> None:
        received_2.append(event)

    bus.subscribe(BusTestEvent, handler1)
    bus.subscribe(BusTestEvent, handler2)

    bus.emit(BusTestEvent(value=99))

    assert len(received_1) == 1
    assert len(received_2) == 1
    assert received_1[0].value == 99
    assert received_2[0].value == 99


def test_bus_unsubscribe(bus: EventBus) -> None:
    """Test unsubscribing handlers."""
    call_count = 0

    def handler(_event: BusTestEvent) -> None:
        nonlocal call_count
        call_count += 1

    bus.subscribe(BusTestEvent, handler)
    bus.emit(BusTestEvent(value=1))
    assert call_count == 1

    bus.unsubscribe(BusTestEvent, handler)
    bus.emit(BusTestEvent(value=2))
    assert call_count == 1  # Should not increment


def test_bus_per_client_isolation() -> None:
    """Test that different client IDs create isolated buses."""
    bus1 = EventBus(client_id="client-1", config=BusConfig(trace=False))
    bus2 = EventBus(client_id="client-2", config=BusConfig(trace=False))

    received_1: list[BusTestEvent] = []
    received_2: list[BusTestEvent] = []

    def handler1(event: BusTestEvent) -> None:
        received_1.append(event)

    def handler2(event: BusTestEvent) -> None:
        received_2.append(event)

    bus1.subscribe(BusTestEvent, handler1)
    bus2.subscribe(BusTestEvent, handler2)

    # Emit on bus1 - only handler1 should receive it
    bus1.emit(BusTestEvent(value=1))
    assert len(received_1) == 1
    assert len(received_2) == 0

    # Emit on bus2 - only handler2 should receive it
    bus2.emit(BusTestEvent(value=2))
    assert len(received_1) == 1  # Unchanged
    assert len(received_2) == 1


def test_bus_clear(bus: EventBus) -> None:
    """Test clearing all subscriptions."""
    call_count = 0

    def handler(_event: BusTestEvent) -> None:
        nonlocal call_count
        call_count += 1

    bus.subscribe(BusTestEvent, handler)
    bus.emit(BusTestEvent(value=1))
    assert call_count == 1

    bus.clear()
    bus.emit(BusTestEvent(value=2))
    assert call_count == 1  # Should not increment


def test_bus_type_safety() -> None:
    """Test that events are routed by concrete type."""
    bus = EventBus(client_id="test", config=BusConfig(trace=False))

    file_selection_received: list[FileSelection] = []

    def handler(event: FileSelection) -> None:
        file_selection_received.append(event)

    # Subscribe without phase filter to receive all FileSelection events
    bus.subscribe(FileSelection, handler)

    # Emit FileSelection - handler should receive it
    bus.emit(
        FileSelection(
            path="/test.tif",
            file=None,
            origin=SelectionOrigin.FILE_TABLE,
            phase="intent",
        )
    )
    assert len(file_selection_received) == 1

    # Emit different event type - handler should not receive it
    bus.emit(BusTestEvent(value=42))
    assert len(file_selection_received) == 1  # Unchanged


def test_bus_unsubscribe_removes_all_phases(bus: EventBus) -> None:
    """Unsubscribe with phase=None should remove intent and state handlers."""
    call_count = 0

    def handler(_event: FileSelection) -> None:
        nonlocal call_count
        call_count += 1

    bus.subscribe_intent(FileSelection, handler)
    bus.subscribe_state(FileSelection, handler)
    bus.unsubscribe(FileSelection, handler)

    bus.emit(
        FileSelection(
            path="/test.tif",
            file=None,
            origin=SelectionOrigin.FILE_TABLE,
            phase="intent",
        )
    )
    bus.emit(
        FileSelection(
            path="/test.tif",
            file=None,
            origin=SelectionOrigin.FILE_TABLE,
            phase="state",
        )
    )

    assert call_count == 0


def test_bus_phase_filters(bus: EventBus) -> None:
    """Phase filters should route only matching events."""
    intent_calls = 0
    state_calls = 0

    def intent_handler(_event: FileSelection) -> None:
        nonlocal intent_calls
        intent_calls += 1

    def state_handler(_event: FileSelection) -> None:
        nonlocal state_calls
        state_calls += 1

    bus.subscribe_intent(FileSelection, intent_handler)
    bus.subscribe_state(FileSelection, state_handler)

    bus.emit(
        FileSelection(
            path="/test.tif",
            file=None,
            origin=SelectionOrigin.FILE_TABLE,
            phase="intent",
        )
    )
    bus.emit(
        FileSelection(
            path="/test.tif",
            file=None,
            origin=SelectionOrigin.FILE_TABLE,
            phase="state",
        )
    )

    assert intent_calls == 1
    assert state_calls == 1


def test_bus_unsubscribe_noop_on_missing(bus: EventBus) -> None:
    """Unsubscribing an unknown handler should not raise."""
    def handler(_event: FileSelection) -> None:
        pass

    bus.unsubscribe(FileSelection, handler)

