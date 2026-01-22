"""Tests for file selection flow to verify no feedback loops."""

from __future__ import annotations

from pathlib import Path

import pytest

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.app_state_bridge import AppStateBridgeController
from kymflow.gui_v2.controllers.file_selection_controller import FileSelectionController
from kymflow.gui_v2.events import FileSelection, ROISelection, SelectionOrigin


def test_selection_flow_preserves_origin(bus: EventBus, app_state: AppState) -> None:
    """Test that SelectionOrigin is preserved through the selection flow."""
    # Set up controllers
    bridge = AppStateBridgeController(app_state, bus)
    controller = FileSelectionController(app_state, bus)

    # Track FileSelection (phase="state") events
    received_events: list[FileSelection] = []

    def handler(event: FileSelection) -> None:
        if event.phase == "state":
            received_events.append(event)

    bus.subscribe_state(FileSelection, handler)

    # Emit FileSelection (phase="intent") with FILE_TABLE origin
    bus.emit(
        FileSelection(
            path="/test.tif",
            file=None,
            origin=SelectionOrigin.FILE_TABLE,
            phase="intent",
        )
    )

    # Should emit FileSelection (phase="state") with FILE_TABLE origin preserved
    assert len(received_events) > 0
    assert received_events[-1].origin == SelectionOrigin.FILE_TABLE
    assert received_events[-1].phase == "state"


def test_selection_flow_no_loop_on_file_table_origin(
    bus: EventBus, app_state: AppState
) -> None:
    """Test that FILE_TABLE origin prevents feedback loops."""
    # Set up controllers
    bridge = AppStateBridgeController(app_state, bus)
    controller = FileSelectionController(app_state, bus)

    # Track how many times FileSelection (phase="state") is emitted
    event_count = 0

    def handler(_event: FileSelection) -> None:
        nonlocal event_count
        if _event.phase == "state":
            event_count += 1

    bus.subscribe_state(FileSelection, handler)

    # Emit FileSelection (phase="intent") from table
    bus.emit(
        FileSelection(
            path="/test.tif",
            file=None,
            origin=SelectionOrigin.FILE_TABLE,
            phase="intent",
        )
    )

    # Should emit FileSelection (phase="state") once (not loop)
    assert event_count == 1

