"""Controller for handling file selection events from the UI.

This module provides a controller that translates user selection intents
(FileSelection phase="intent") into AppState updates, preserving the
selection origin to prevent feedback loops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import FileSelection, SelectionOrigin

if TYPE_CHECKING:
    pass


class FileSelectionController:
    """Apply file selection events to AppState.

    This controller handles selection intent events from the UI (typically
    from the file table) and updates AppState accordingly. It preserves
    the SelectionOrigin through AppState so that downstream bindings can
    prevent feedback loops.

    Selection Flow:
        1. User clicks table row → FileTableView emits FileSelection(phase="intent", origin=FILE_TABLE)
        2. This controller receives event → calls AppState.select_file(origin=FILE_TABLE)
        3. AppState callback → AppStateBridge emits FileSelection(phase="state", origin=FILE_TABLE)
        4. FileTableBindings receives event, checks origin, ignores if FILE_TABLE
           (prevents re-selecting the table, which would cause a loop)

    Note: Two events (intent + state) are expected and correct:
    - Intent event: User action (phase="intent") - what the user wants to do
    - State event: State change (phase="state") - what actually happened
    This allows views to react to state changes without triggering feedback loops.

    Attributes:
        _app_state: AppState instance to update.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize file selection controller.

        Subscribes to FileSelection (phase="intent") events from the bus.

        Args:
            app_state: AppState instance to update.
            bus: EventBus instance to subscribe to.
        """
        self._app_state: AppState = app_state
        bus.subscribe_intent(FileSelection, self._on_file_selected)

    def _on_file_selected(self, e: FileSelection) -> None:
        """Handle FileSelection intent event.

        Updates AppState with the selected file. Handles FILE_TABLE and EXTERNAL
        origins (prevents other origins from triggering state changes inappropriately).

        Args:
            e: FileSelection event (phase="intent") containing the file path and origin.
        """
        # Handle FILE_TABLE and EXTERNAL origins
        # In the future, other sources (e.g., image viewer) could also emit FileSelection
        if e.origin not in (SelectionOrigin.FILE_TABLE, SelectionOrigin.EXTERNAL):
            return

        if e.path is None:
            self._app_state.select_file(None, origin=e.origin)
            return

        # Find matching file in AppState file list
        match = None
        for f in self._app_state.files:
            if str(f.path) == e.path:
                match = f
                break

        # Update AppState with selection (origin preserved for feedback loop prevention)
        self._app_state.select_file(match, origin=e.origin)