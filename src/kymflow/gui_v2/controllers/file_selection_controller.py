"""Controller for handling file selection events from the UI.

This module provides a controller that translates user selection intents
(FileSelected, FilesSelected events) into AppState updates, preserving
the selection origin to prevent feedback loops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import FileSelected, FilesSelected, SelectionOrigin

if TYPE_CHECKING:
    pass


class FileSelectionController:
    """Apply file selection events to AppState.

    This controller handles selection intent events from the UI (typically
    from the file table) and updates AppState accordingly. It preserves
    the SelectionOrigin through AppState so that downstream bindings can
    prevent feedback loops.

    Selection Flow:
        1. User clicks table row → FileTableView emits FileSelected(origin=FILE_TABLE)
        2. This controller receives event → calls AppState.select_file(origin=FILE_TABLE)
        3. AppState callback → AppStateBridge emits SelectedFileChanged(origin=FILE_TABLE)
        4. FileTableBindings receives event, checks origin, ignores if FILE_TABLE
           (prevents re-selecting the table, which would cause a loop)

    Attributes:
        _app_state: AppState instance to update.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize file selection controller.

        Subscribes to FileSelected and FilesSelected events from the bus.

        Args:
            app_state: AppState instance to update.
            bus: EventBus instance to subscribe to.
        """
        self._app_state: AppState = app_state
        bus.subscribe(FileSelected, self._on_file_selected)
        bus.subscribe(FilesSelected, self._on_files_selected)

    def _on_file_selected(self, e: FileSelected) -> None:
        """Handle FileSelected event.

        Updates AppState with the selected file, but only if the origin
        is FILE_TABLE (prevents external selections from triggering state
        changes inappropriately).

        Args:
            e: FileSelected event containing the file path and origin.
        """
        # v2: only FileTable drives selection for now
        # In the future, other sources (e.g., image viewer) could also emit FileSelected
        if e.origin != SelectionOrigin.FILE_TABLE:
            return

        if e.path is None:
            self._app_state.select_file(None, origin=SelectionOrigin.FILE_TABLE)
            return

        # Find matching file in AppState file list
        match = None
        for f in self._app_state.files:
            if str(f.path) == e.path:
                match = f
                break

        # Update AppState with selection (origin preserved for feedback loop prevention)
        self._app_state.select_file(match, origin=SelectionOrigin.FILE_TABLE)

    def _on_files_selected(self, e: FilesSelected) -> None:
        """Handle FilesSelected event (multi-selection).

        Currently converts to single selection (first path) since AppState
        only supports single file selection (matching v1 behavior).

        Args:
            e: FilesSelected event containing list of file paths and origin.
        """
        # v2 still drives AppState with a single selected file (like v1)
        if not e.paths:
            self._app_state.select_file(None, origin=SelectionOrigin.FILE_TABLE)
            return

        # Convert multi-selection to single (take first)
        self._on_file_selected(FileSelected(path=e.paths[0], origin=SelectionOrigin.FILE_TABLE))