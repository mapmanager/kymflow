"""Controller for handling next/previous file navigation events.

This module provides a controller that handles NextPrevFileEvent intent events,
finds the next or previous file in the file list, and emits a FileSelection
event if a valid file is found.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import FileSelection, NextPrevFileEvent, SelectionOrigin
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class NextPrevFileController:
    """Handle next/previous file navigation events.

    This controller subscribes to NextPrevFileEvent (intent phase) and:
    1. Finds the current file index in AppState.files
    2. Calculates the target index (current ± 1 based on direction)
    3. If valid, emits FileSelection(phase="intent", origin=EXTERNAL)
    4. If invalid (at boundary), event terminates silently

    Flow:
        1. NextPrevFileEvent(phase="intent") → controller finds next/prev file
        2. If found: emits FileSelection(phase="intent", origin=EXTERNAL)
        3. FileSelectionController handles it → AppState.select_file()
        4. AppStateBridge emits FileSelection(phase="state")
        5. Views update via bindings

    Attributes:
        _app_state: AppState instance to query file list.
        _bus: EventBus instance to emit FileSelection events.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize next/previous file controller.

        Subscribes to NextPrevFileEvent (phase="intent") events from the bus.

        Args:
            app_state: AppState instance to query file list.
            bus: EventBus instance to subscribe to and emit events.
        """
        self._app_state: AppState = app_state
        self._bus: EventBus = bus
        bus.subscribe_intent(NextPrevFileEvent, self._on_next_prev_file)

    def _on_next_prev_file(self, e: NextPrevFileEvent) -> None:
        """Handle NextPrevFileEvent intent event.

        Finds the next or previous file in the file list and emits
        FileSelection if found. If at boundary (first/last file), event
        terminates silently.

        Args:
            e: NextPrevFileEvent (phase="intent") containing direction.
        """
        # Get current file
        current_file = self._app_state.selected_file
        if current_file is None:
            logger.debug("NextPrevFileEvent: no file selected, ignoring")
            return

        # Get file list
        files = list(self._app_state.files)
        if len(files) == 0:
            logger.debug("NextPrevFileEvent: no files in list, ignoring")
            return

        # Find current file index
        current_index = None
        current_path_str = str(current_file.path)
        for i, file in enumerate(files):
            if str(file.path) == current_path_str:
                current_index = i
                break

        if current_index is None:
            logger.debug(
                f"NextPrevFileEvent: current file {current_path_str} not found in file list, ignoring"
            )
            return

        # Calculate target index
        if e.direction == "Next File":
            target_index = current_index + 1
        else:  # "Prev File"
            target_index = current_index - 1

        # Validate target index
        if target_index < 0 or target_index >= len(files):
            # At boundary - show failure notification
            failure_message = (
                "No previous file" if e.direction == "Prev File" else "No next file"
            )
            ui.notify(failure_message, type="info")
            logger.debug(
                f"NextPrevFileEvent: target index {target_index} out of range [0, {len(files)}), ignoring"
            )
            return

        # Get target file and emit FileSelection
        target_file = files[target_index]
        target_path = str(target_file.path)
        target_filename = Path(target_path).name
        logger.debug(
            f"NextPrevFileEvent: navigating from index {current_index} to {target_index} ({target_path})"
        )

        # Show success notification
        ui.notify(f"Switched to: {target_filename}", type="positive")

        self._bus.emit(
            FileSelection(
                path=target_path,
                file=None,  # Set in state phase
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )
