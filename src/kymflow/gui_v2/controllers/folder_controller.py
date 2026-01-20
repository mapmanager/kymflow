"""Controller for handling folder selection events.

This module provides a controller that translates FolderChosen events
from the UI into AppState folder loading operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kymflow.gui.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_folder import FolderChosen

if TYPE_CHECKING:
    pass


class FolderController:
    """Controller that applies folder selection events to AppState.

    This controller handles FolderChosen events (typically from FolderSelectorView)
    and triggers AppState.load_folder(), which scans the folder for kymograph
    files and updates the file list.

    Flow:
        1. User selects folder → FolderSelectorView emits FolderChosen
        2. This controller receives event → calls AppState.load_folder()
        3. AppState scans folder and updates file list
        4. AppState callback → AppStateBridge emits FileListChanged
        5. FileTableBindings receives event → updates file table

    Attributes:
        _app_state: AppState instance to update.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize folder controller.

        Subscribes to FolderChosen events from the bus.

        Args:
            app_state: AppState instance to update.
            bus: EventBus instance to subscribe to.
        """
        self._app_state: AppState = app_state
        bus.subscribe(FolderChosen, self._on_folder_chosen)

    def _on_folder_chosen(self, e: FolderChosen) -> None:
        """Handle FolderChosen event.

        Loads the specified folder in AppState, which will trigger file
        scanning and emit FileListChanged via the bridge.

        Args:
            e: FolderChosen event containing the folder path.
        """
        # Explicitly use current folder_depth from app_state to ensure UI setting is respected
        self._app_state.load_folder(Path(e.folder), depth=self._app_state.folder_depth)
