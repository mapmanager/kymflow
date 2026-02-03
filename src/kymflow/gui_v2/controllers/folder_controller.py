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
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

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

        Loads the specified folder or file in AppState, which will trigger file
        scanning and emit FileListChanged via the bridge.
        
        If depth is provided in the event, sets app_state.folder_depth before loading (for folders only).
        After successful load, persists the path to user config.

        Args:
            e: FolderChosen event containing the path (folder or file) and optional depth.
        """
        path = Path(e.folder)
        
        # Determine if file or folder
        is_file = path.is_file()
        is_folder = path.is_dir()
        
        if not (is_file or is_folder):
            # Updated: generic message for both files and folders
            ui.notify(f"Path does not exist: {path}", type="warning")
            return
        
        if self._app_state.files and self._app_state.files.any_dirty_analysis():
            self._show_unsaved_dialog(path)
            return
        
        # Simplified: load_folder() accepts both files and folders
        # For files, depth is ignored by AcqImageList
        # For folders, use provided depth or current app_state depth
        depth = e.depth if e.depth is not None else self._app_state.folder_depth
        if e.depth is not None and is_folder:
            # Only update folder_depth for folders (not needed for files)
            self._app_state.folder_depth = depth
        
        # Load path (file or folder) - depth will be ignored for files
        self._app_state.load_folder(path, depth=depth)
        
        # Persist to config (depth=0 for files, actual depth for folders)
        if self._user_config is not None:
            config_depth = 0 if is_file else depth
            self._user_config.push_recent_folder(str(path), depth=config_depth)

    def _load_folder(self, folder: Path) -> None:
        """Load folder with current depth and persist to config.
        
        Deprecated: Use _on_folder_chosen() directly instead.
        """
        self._app_state.load_folder(folder, depth=self._app_state.folder_depth)
        if self._user_config is not None:
            self._user_config.push_recent_folder(str(folder), depth=self._app_state.folder_depth)

    def _show_unsaved_dialog(self, path: Path) -> None:
        """Prompt before switching folders/files if unsaved changes exist.
        
        path is the new path to switch to
        current_folder is the current folder
        current_file is the current file selected in the file table view (don't use)
        """
        # Get the current folder/file (the one we're switching FROM)
        current_folder = self._app_state.folder
        
        # incorrect, this is the file selected in the file table view
        # current_file = self._app_state.selected_file
        
        # logger.debug(f'path:{path}')
        # logger.debug(f'current_folder:{current_folder}')
        # logger.debug(f'current_file:{current_file}')

        # Determine current path and type
        # if current_file is not None and current_file.path is not None:
        #     current_path = Path(current_file.path)
        #     current_path_type = "file" if current_path.is_file() else "folder"
        if current_folder is not None:
            current_path = current_folder
            current_path_type = "folder"
        else:
            # Fallback if we can't determine current path
            # will never get here
            logger.error('should never be here')
            current_path = Path(".")
            current_path_type = "folder"
        
        # Determine destination path type
        dest_path_type = "file" if path.is_file() else "folder"
        
        with ui.dialog() as dialog, ui.card():
            # ui.label(f"Unsaved changes in {current_path_type}").classes("text-lg font-semibold")
            # ui.label(f"{current_path_type}: {current_path}").classes("text-sm")
            ui.label('Unsaved changes in file/folder').classes("text-lg font-semibold")
            ui.label(
                "Analysis/metadata edits are not saved. "
                f"If you switch to {dest_path_type} '{path.name}' now, those changes will be lost."
            ).classes("text-sm")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("outline")
                ui.button(
                    f"Switch to {dest_path_type}",
                    on_click=lambda: self._confirm_switch_path(dialog, path),
                ).props("color=red")

        dialog.open()

    def _confirm_switch_path(self, dialog, path: Path) -> None:
        """Confirm path switch after unsaved changes warning."""
        dialog.close()
        # Determine depth based on path type
        is_file = path.is_file()
        depth = 0 if is_file else self._app_state.folder_depth
        self._app_state.load_folder(path, depth=depth)
        if self._user_config is not None:
            config_depth = 0 if is_file else depth
            self._user_config.push_recent_folder(str(path), depth=config_depth)