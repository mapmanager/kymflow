"""Controller for handling path selection events.

This module provides a controller that translates SelectPathEvent intent events
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

    This controller handles SelectPathEvent intent events (typically from FolderSelectorView)
    and triggers AppState.load_folder(), which scans the path for kymograph
    files and updates the file list.

    Flow:
        1. User selects path → FolderSelectorView emits SelectPathEvent(phase="intent")
        2. This controller receives intent event → validates and loads path
        3. On success: emits SelectPathEvent(phase="state")
        4. On cancel: emits CancelSelectPathEvent
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

        Subscribes to SelectPathEvent intent-phase events from the bus.

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
        After successful load, emits SelectPathEvent(phase="state") and persists the path to user config.
        On cancellation, emits CancelSelectPathEvent.

        Args:
            e: SelectPathEvent (phase="intent") containing the path and optional depth.
        """
        new_path = Path(e.new_path)
        
        # Determine if file or folder
        is_file = new_path.is_file()
        is_folder = new_path.is_dir()
        
        # Get current path from app_state (always the actual selected path, file or folder)
        current_path = str(self._app_state.folder) if self._app_state.folder else None

        if not (is_file or is_folder):
            ui.notify(f"Path does not exist: {new_path}", type="warning")
            if current_path:
                self._bus.emit(CancelSelectPathEvent(previous_path=current_path))
            return
        
        if self._app_state.files and self._app_state.files.any_dirty_analysis():
            original_depth = e.depth
            self._show_unsaved_dialog(new_path, current_path, original_depth)
            return
        
        # For files, depth is always 0 (ignored by AcqImageList)
        # For folders, use event depth or current app_state depth
        if is_file:
            depth = 0
        else:
            depth = e.depth if e.depth is not None else self._app_state.folder_depth
            if e.depth is not None:
                self._app_state.folder_depth = depth
        
        self._app_state.load_folder(new_path, depth=depth)
        
        if self._user_config is not None:
            config_depth = 0 if is_file else depth
            self._user_config.push_recent_path(str(new_path), depth=config_depth)
        
        from nicegui import app
        if is_file:
            title = f'KymFlow - {new_path.name}'
        else:
            title = f'KymFlow - {new_path.name}/'
        
        logger.debug(f'=== setting window title to "{title}"')
        app.native.main_window.set_title(title)
        
        # import asyncio
        # _size = ui.run().io(app.native.main_window.get_size())
        # # _size = app.native.main_window.get_size()
        # logger.debug(f'=== window size: {_size}')

        # Emit state event to confirm successful load
        # logger.debug('-->> emit SelectPathEvent')
        self._bus.emit(SelectPathEvent(
            new_path=str(new_path),
            depth=depth,
            phase="state",
        ))

    def _load_folder(self, path: Path) -> None:
        """Load path with current depth and persist to config.
        
        Deprecated: Use _on_select_path_event() directly instead.
        
        Note: This method doesn't properly handle file vs folder depth (always uses app_state.folder_depth).
        Use _on_select_path_event() which correctly handles depth for both files and folders.
        """
        is_file = path.is_file()
        depth = 0 if is_file else self._app_state.folder_depth
        self._app_state.load_folder(path, depth=depth)
        if self._user_config is not None:
            config_depth = 0 if is_file else depth
            self._user_config.push_recent_path(str(path), depth=config_depth)

    def _show_unsaved_dialog(self, new_path: Path, previous_path_str: str | None, original_depth: int | None) -> None:
        """Prompt before switching paths if unsaved changes exist.
        
        Args:
            new_path: The new path to switch to.
            previous_path_str: The previous path (for revert on cancel).
            original_depth: The depth from the original SelectPathEvent (for folders only).
        """


        dest_path_type = "file" if new_path.is_file() else "folder"
        
        prev_path_type = "folder"
        if previous_path_str:
            previous_path = Path(previous_path_str)
            prev_path_type = "file" if previous_path.is_file() else "folder"
        
        with ui.dialog() as dialog, ui.card():
            ui.label(f'Unsaved changes in {prev_path_type}').classes("text-lg font-semibold")
            if previous_path_str:
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
                    on_click=lambda: self._confirm_switch_path(dialog, new_path, previous_path_str, original_depth),
                ).props("color=red")

        dialog.open()
    
    def _on_dialog_cancel(self, dialog, previous_path: str | None) -> None:
        """Handle dialog cancellation - emit cancellation event."""
        dialog.close()
        if previous_path:
            self._bus.emit(CancelSelectPathEvent(previous_path=previous_path))

    def _confirm_switch_path(self, dialog, path: Path, previous_path: str | None, original_depth: int | None) -> None:
        """Confirm path switch after unsaved changes warning.
        
        Args:
            dialog: The dialog to close.
            path: The new path to switch to.
            previous_path: The previous path (for revert on cancel).
            original_depth: The depth from the original SelectPathEvent (for folders only).
        """
        dialog.close()
        is_file = path.is_file()
        is_folder = path.is_dir()
        
        if is_file:
            depth = 0
        elif original_depth is not None:
            depth = original_depth
        else:
            depth = self._app_state.folder_depth
        
        if is_folder and original_depth is not None:
            self._app_state.folder_depth = original_depth
        
        self._app_state.load_folder(path, depth=depth)
        
        if self._user_config is not None:
            config_depth = 0 if is_file else depth
            self._user_config.push_recent_path(str(path), depth=config_depth)
        
        # Emit state event to confirm successful load
        self._bus.emit(SelectPathEvent(
            new_path=str(path),
            depth=depth,
            phase="state",
        ))