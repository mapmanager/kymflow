"""Controller for handling folder selection events.

This module provides a controller that translates FolderChosen events
from the UI into AppState folder loading operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_folder import FolderChosen
from kymflow.core.user_config import UserConfig

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
        _user_config: UserConfig instance for persisting folder selections.
    """

    def __init__(self, app_state: AppState, bus: EventBus, user_config: UserConfig | None = None) -> None:
        """Initialize folder controller.

        Subscribes to FolderChosen events from the bus.

        Args:
            app_state: AppState instance to update.
            bus: EventBus instance to subscribe to.
            user_config: Optional UserConfig instance for persisting folder selections.
        """
        self._app_state: AppState = app_state
        self._user_config: UserConfig | None = user_config
        bus.subscribe(FolderChosen, self._on_folder_chosen)

    def _on_folder_chosen(self, e: FolderChosen) -> None:
        """Handle FolderChosen event.

        Loads the specified folder in AppState, which will trigger file
        scanning and emit FileListChanged via the bridge.
        
        If depth is provided in the event, sets app_state.folder_depth before loading.
        After successful load, persists the folder to user config.

        Args:
            e: FolderChosen event containing the folder path and optional depth.
        """
        # If depth is provided, set it before loading (e.g., from config or recent select)
        if e.depth is not None:
            self._app_state.folder_depth = e.depth
        
        # Load folder with current depth (either from event or existing app_state value)
        self._app_state.load_folder(Path(e.folder), depth=self._app_state.folder_depth)
        
        # Persist to user config after successful load
        if self._user_config is not None:
            self._user_config.push_recent_folder(e.folder, depth=self._app_state.folder_depth)
            self._user_config.save()