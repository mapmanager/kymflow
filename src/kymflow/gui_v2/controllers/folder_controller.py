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
from kymflow.gui_v2.window_utils import set_window_title_for_path
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

        Loads the specified path (folder, file, or CSV) in AppState, which will trigger file
        scanning and emit FileListChanged via the bridge.
        
        Automatically detects CSV files by checking if the path exists, is a file, and has .csv extension.
        If depth is provided in the event, sets app_state.folder_depth before loading (for folders only).
        After successful load, emits SelectPathEvent(phase="state") and persists the path to user config.
        On cancellation, emits CancelSelectPathEvent.

        Args:
            e: SelectPathEvent (phase="intent") containing the path and optional depth.
        """
        new_path = Path(e.new_path)
        current_path = str(self._app_state.folder) if self._app_state.folder else None
        
        # Auto-detect CSV: must exist, be a file, and have .csv extension
        is_csv = new_path.exists() and new_path.is_file() and new_path.suffix.lower() == '.csv'
        
        if is_csv:
            self._handle_csv_event_from_path(new_path, current_path)
            return
        
        # Determine if file or folder
        is_file = new_path.is_file()
        is_folder = new_path.is_dir()

        if not (is_file or is_folder):
            logger.error(f'Path does not exist: "{new_path}"')
            ui.notify(f"Path does not exist: {new_path}", type="warning")
            if current_path:
                logger.debug(f'emitting CancelSelectPathEvent for previous path: "{current_path}"')
                self._bus.emit(CancelSelectPathEvent(previous_path=current_path))
            return
        
        # Calculate depth early (needed for both dirty and non-dirty paths)
        # For files, depth is always 0 (ignored by AcqImageList)
        # For folders, use event depth or current app_state depth
        if is_file:
            depth = 0
        else:
            depth = e.depth if e.depth is not None else self._app_state.folder_depth
            if e.depth is not None:
                self._app_state.folder_depth = depth
        
        # Check for unsaved changes
        if self._app_state.files and self._app_state.files.any_dirty_analysis():
            self._show_unsaved_dialog(new_path, current_path, depth)
            return
        
        # Not dirty - proceed directly
        self._finally_set_path(new_path, depth, is_file)
    
    def _handle_csv_event_from_path(self, csv_path: Path, current_path: str | None) -> None:
        """Handle CSV file loading from path.
        
        Args:
            csv_path: Path to CSV file (already validated to exist and be .csv).
            current_path: Current path from app_state (for cancellation).
        """
        # Check for unsaved changes
        if self._app_state.files and self._app_state.files.any_dirty_analysis():
            self._show_unsaved_dialog(csv_path, current_path, 0)
            return
        
        # Not dirty - proceed with CSV load
        try:
            # Load CSV (will validate 'path' column inside)
            self._app_state.load_folder(csv_path, depth=0)
            
            # Persist to user config
            if self._user_config is not None:
                self._user_config.push_recent_csv(str(csv_path))
            
            # Set window title
            set_window_title_for_path(csv_path, is_file=True)
            
            # Emit state event
            self._bus.emit(SelectPathEvent(
                new_path=str(csv_path),
                depth=0,
                phase="state",
            ))
            
            ui.notify(f"Loaded CSV: {csv_path.name}", type="positive")
            
        except ValueError as ve:
            # CSV validation error (missing 'path' column, etc.)
            error_msg = str(ve)
            logger.error(f"CSV validation error: {error_msg}")
            ui.notify(f"CSV error: {error_msg}", type="negative")
            if current_path:
                self._bus.emit(CancelSelectPathEvent(previous_path=current_path))
        except Exception as exc:
            # Other errors (pandas read error, etc.)
            error_msg = str(exc)
            logger.error(f"Failed to load CSV: {error_msg}", exc_info=True)
            ui.notify(f"Failed to load CSV: {error_msg}", type="negative")
            if current_path:
                self._bus.emit(CancelSelectPathEvent(previous_path=current_path))

    def _finally_set_path(self, path: Path, depth: int, is_file: bool) -> None:
        """Finalize path switch: load folder, save config, set title, emit event.
        
        This is called by both the non-dirty path and the confirmed dirty path.
        
        Args:
            path: The path to switch to.
            depth: The depth to use (0 for files, folder depth for folders).
            is_file: True if path is a file, False if folder.
        """
        # Load the folder/file
        self._app_state.load_folder(path, depth=depth)
        
        # Persist to user config
        if self._user_config is not None:
            config_depth = 0 if is_file else depth
            self._user_config.push_recent_path(str(path), depth=config_depth)
        
        # Set window title
        set_window_title_for_path(path, is_file=is_file)
        
        # Emit state event to confirm successful load
        self._bus.emit(SelectPathEvent(
            new_path=str(path),
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

    def _show_unsaved_dialog(self, new_path: Path, previous_path_str: str | None, depth: int) -> None:
        """Prompt before switching paths if unsaved changes exist.
        
        Args:
            new_path: The new path to switch to.
            previous_path_str: The previous path (for revert on cancel).
            depth: The calculated depth to use (already computed from event).
        """
        # Determine destination type (CSV, file, or folder)
        if new_path.is_file() and new_path.suffix.lower() == '.csv':
            dest_path_type = "CSV"
        elif new_path.is_file():
            dest_path_type = "file"
        else:
            dest_path_type = "folder"
        
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
                    on_click=lambda: self._confirm_switch_path(dialog, new_path, previous_path_str, depth),
                ).props("color=red")

        dialog.open()
    
    def _on_dialog_cancel(self, dialog, previous_path: str | None) -> None:
        """Handle dialog cancellation - emit cancellation event."""
        dialog.close()
        if previous_path:
            self._bus.emit(CancelSelectPathEvent(previous_path=previous_path))

    def _confirm_switch_path(self, dialog, path: Path, previous_path: str | None, depth: int) -> None:
        """Confirm path switch after unsaved changes warning.
        
        Args:
            dialog: The dialog to close.
            path: The new path to switch to.
            previous_path: The previous path (for revert on cancel).
            depth: The depth to use (already calculated, passed from dialog).
        """
        dialog.close()
        
        # Check if CSV
        is_csv = path.is_file() and path.suffix.lower() == '.csv'
        
        if is_csv:
            # Handle CSV loading
            try:
                self._app_state.load_folder(path, depth=0)
                
                if self._user_config is not None:
                    self._user_config.push_recent_csv(str(path))
                
                set_window_title_for_path(path, is_file=True)
                
                self._bus.emit(SelectPathEvent(
                    new_path=str(path),
                    depth=0,
                    phase="state",
                ))
            except Exception as exc:
                error_msg = str(exc)
                logger.error(f"Failed to load CSV: {error_msg}", exc_info=True)
                ui.notify(f"Failed to load CSV: {error_msg}", type="negative")
                if previous_path:
                    self._bus.emit(CancelSelectPathEvent(previous_path=previous_path))
            return
        
        is_file = path.is_file()
        
        # Update folder_depth if this is a folder (depth was calculated from event)
        if not is_file and depth != self._app_state.folder_depth:
            self._app_state.folder_depth = depth
        
        # Use the shared finalization logic
        self._finally_set_path(path, depth, is_file)