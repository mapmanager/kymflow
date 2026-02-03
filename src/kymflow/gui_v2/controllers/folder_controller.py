"""Controller for handling path selection events.

This module provides a controller that translates PathChosen events
from the UI into AppState path loading operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_folder import SelectPathEvent, CancelSelectPathEvent
from kymflow.core.user_config import UserConfig
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    pass


class FolderController:
    """Controller that applies path selection events to AppState.

    This controller handles PathChosen events (typically from FolderSelectorView)
    and triggers AppState.load_folder(), which scans the path for kymograph
    files and updates the file list.

    Flow:
        1. User selects path → FolderSelectorView emits PathChosen(phase="intent")
        2. This controller receives intent event → validates and loads path
        3. On success: emits PathChosen(phase="state")
        4. On cancel: emits PathChosenCancelled
        5. AppState scans path and updates file list
        6. AppState callback → AppStateBridge emits FileListChanged
        7. FileTableBindings receives event → updates file table

    Attributes:
        _app_state: AppState instance to update.
        _user_config: UserConfig instance for persisting path selections.
        _bus: EventBus instance for emitting state/cancel events.
    """

    def __init__(self, app_state: AppState, bus: EventBus, user_config: UserConfig | None = None) -> None:
        """Initialize folder controller.

        Subscribes to PathChosen intent-phase events from the bus.

        Args:
            app_state: AppState instance to update.
            bus: EventBus instance to subscribe to.
            user_config: Optional UserConfig instance for persisting path selections.
        """
        self._app_state: AppState = app_state
        self._user_config: UserConfig | None = user_config
        self._bus: EventBus = bus
        bus.subscribe_intent(SelectPathEvent, self._on_select_path_event)

    def _on_select_path_event(self, e: SelectPathEvent) -> None:
        """Handle SelectPathEvent intent event.

        Loads the specified path (folder or file) in AppState, which will trigger file
        scanning and emit FileListChanged via the bridge.
        
        If depth is provided in the event, sets app_state.folder_depth before loading (for folders only).
        After successful load, emits PathChosen(phase="state") and persists the path to user config.
        On cancellation, emits PathChosenCancelled.

        Args:
            e: PathChosen event (phase="intent") containing the path and optional depth.
        """
        new_path = Path(e.new_path)
        
        # Determine if file or folder
        is_file = new_path.is_file()
        is_folder = new_path.is_dir()
        
        # get current path from app_state
        # bug: this will be path to folder or path to enclosing folder (for file selection)
        current_path = str(self._app_state.folder) if self._app_state.folder else None

        if not (is_file or is_folder):
            # Updated: generic message for both files and folders
            ui.notify(f"Path does not exist: {new_path}", type="warning")
            # Emit cancellation since path doesn't exist
            if current_path:
                self._bus.emit(CancelSelectPathEvent(previous_path=current_path))
            return
        
        # allow user to cancel if there are unsaved changes
        if self._app_state.files and self._app_state.files.any_dirty_analysis():
            self._show_unsaved_dialog(new_path, current_path)
            return
        
        # Simplified: load_folder() accepts both files and folders
        # For files, depth is ignored by AcqImageList
        # For folders, use provided depth or current app_state depth
        depth = e.depth if e.depth is not None else self._app_state.folder_depth
        if e.depth is not None and is_folder:
            # Only update folder_depth for folders (not needed for files)
            self._app_state.folder_depth = depth
        
        # Load path (file or folder) - depth will be ignored for files
        self._app_state.load_folder(new_path, depth=depth)
        
        # Persist to config (depth=0 for files, actual depth for folders)
        if self._user_config is not None:
            config_depth = 0 if is_file else depth
            self._user_config.push_recent_folder(str(new_path), depth=config_depth)
        
        # Emit state event to confirm successful load
        self._bus.emit(SelectPathEvent(
            new_path=str(new_path),
            depth=depth,
            phase="state",
        ))

    def _load_folder(self, path: Path) -> None:
        """Load path with current depth and persist to config.
        
        Deprecated: Use _on_path_chosen() directly instead.
        """
        self._app_state.load_folder(path, depth=self._app_state.folder_depth)
        if self._user_config is not None:
            self._user_config.push_recent_folder(str(path), depth=self._app_state.folder_depth)

    def _show_unsaved_dialog(self, new_path: Path, previous_path_str: str | None) -> None:
        """Prompt before switching paths if unsaved changes exist.
        
        Args:
            path: The new path to switch to.
            previous_path: The previous path (for revert on cancel).
        """

        logger.warning(f'new_path:{new_path}')
        logger.warning(f'previous_path_str:{previous_path_str}')

        previous_path = Path(previous_path_str)

        # Determine destination path type
        prev_path_type = "file" if previous_path.is_file() else "folder"
        dest_path_type = "file" if new_path.is_file() else "folder"
        
        with ui.dialog() as dialog, ui.card():
            ui.label(f'Unsaved changes in {prev_path_type}').classes("text-lg font-semibold")
            ui.label(previous_path_str).classes("text-sm")
            ui.label(f"If you switch to {dest_path_type} '{new_path.name}' now, those changes will be lost."
            ).classes("text-sm")
            with ui.row():
                ui.button(
                    "Cancel",
                    on_click=lambda: self._on_dialog_cancel(dialog, previous_path_str)
                ).props("outline")
                ui.button(
                    f"Switch to {dest_path_type}",
                    on_click=lambda: self._confirm_switch_path(dialog, new_path, previous_path_str),
                ).props("color=red")

        dialog.open()
    
    def _on_dialog_cancel(self, dialog, previous_path: str | None) -> None:
        """Handle dialog cancellation - emit cancellation event."""
        dialog.close()
        if previous_path:
            self._bus.emit(CancelSelectPathEvent(previous_path=previous_path))

    def _confirm_switch_path(self, dialog, path: Path, previous_path: str | None) -> None:
        """Confirm path switch after unsaved changes warning."""
        dialog.close()
        # Determine depth based on path type
        is_file = path.is_file()
        depth = 0 if is_file else self._app_state.folder_depth
        self._app_state.load_folder(path, depth=depth)
        if self._user_config is not None:
            config_depth = 0 if is_file else depth
            self._user_config.push_recent_folder(str(path), depth=config_depth)
        
        # Emit state event to confirm successful load
        self._bus.emit(SelectPathEvent(
            new_path=str(path),
            previous_path=previous_path,
            depth=depth,
            phase="state",
        ))