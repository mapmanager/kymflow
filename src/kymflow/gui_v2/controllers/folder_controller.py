"""Controller for handling folder selection events.

This module provides a controller that translates FolderChosen events
from the UI into AppState folder loading operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

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

        folder = Path(e.folder)
        if not folder.exists():
            ui.notify(f"Folder does not exist: {folder}", type="warning")
            return
        if self._app_state.files and self._app_state.files.any_dirty_analysis():
            self._show_unsaved_dialog(folder)
            return

        self._load_folder(folder)

    def _load_folder(self, folder: Path) -> None:
        """Load folder with current depth and persist to config."""
        self._app_state.load_folder(folder, depth=self._app_state.folder_depth)
        if self._user_config is not None:
            self._user_config.push_recent_folder(str(folder), depth=self._app_state.folder_depth)

    def _show_unsaved_dialog(self, folder: Path) -> None:
        """Prompt before switching folders if unsaved changes exist."""
        with ui.dialog() as dialog, ui.card():
            ui.label("Unsaved changes").classes("text-lg font-semibold")
            ui.label(
                "Analysis/metadata edits are not saved. "
                "If you switch folders now, those changes will be lost."
            ).classes("text-sm")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("outline")
                ui.button(
                    "Switch folder",
                    on_click=lambda: self._confirm_switch_folder(dialog, folder),
                ).props("color=red")

        dialog.open()

    def _confirm_switch_folder(self, dialog, folder: Path) -> None:
        """Confirm folder switch after unsaved changes warning."""
        dialog.close()
        self._load_folder(folder)