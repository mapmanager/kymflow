"""Folder selector view for path selection (folder or file).

This module provides the UI component for selecting folders or files,
emitting SelectPathEvent intent events when paths are selected.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui, app

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import FileSelection, SaveAll, SaveSelected
from kymflow.gui_v2.events_folder import SelectPathEvent, CancelSelectPathEvent
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.gui_v2.client_utils import safe_call
from kymflow.core.user_config import UserConfig
from kymflow.gui_v2._pywebview import _prompt_for_path

logger = get_logger(__name__)

# Error message constants
_ERROR_NATIVE_REQUIRED = "{} selection requires native mode with pywebview. Please restart with KYMFLOW_GUI_NATIVE=1"
_ERROR_NATIVE_WINDOW = "Native window not available. Please ensure you're running with KYMFLOW_GUI_NATIVE=1"


class PathType(str, Enum):
    """Type of path selection (folder, file, or CSV)."""
    FOLDER = "folder"
    FILE = "file"
    CSV = "csv"


def _is_native_mode_available() -> bool:
    """Check if native mode and pywebview are available for folder dialogs.
    
    Returns:
        True if pywebview windows are available (native mode), False otherwise.
    """
    try:
        import webview  # type: ignore
    except Exception:
        return False
    
    windows = getattr(webview, "windows", None)
    return windows is not None and len(windows) > 0


def _validate_native_mode_for_dialog(path_type: PathType) -> tuple[bool, Optional[str]]:
    """Validate that native mode is available for path selection dialog.
    
    Args:
        path_type: Type of path selection (FOLDER, FILE, or CSV).
    
    Returns:
        Tuple of (is_available, error_message). If is_available is True,
        error_message will be None. If False, error_message contains the
        user-facing error message.
    """
    # Check if pywebview module is available at all
    try:
        import webview  # type: ignore
    except ImportError:
        path_type_str = path_type.value.capitalize()
        return False, _ERROR_NATIVE_REQUIRED.format(path_type_str)
    
    native = getattr(app, "native", None)
    main_window = getattr(native, "main_window", None) if native else None
    
    windows = getattr(webview, "windows", None)
    num_windows = len(windows) if windows else 0
    
    if main_window is None and (not windows or num_windows == 0):
        return False, _ERROR_NATIVE_WINDOW
    
    return True, None


OnSaveSelected = Callable[[SaveSelected], None]
OnSaveAll = Callable[[SaveAll], None]


class FolderSelectorView:
    """Folder selector UI that emits SelectPathEvent.

    This view provides UI controls for selecting folders or files:
    - Recent paths dropdown (from UserConfig)
    - "Open folder" button (native file dialog)
    - "Open file" button (native file dialog)
    - Depth input (for folder scanning)
    - Save Selected and Save All buttons

    The view subscribes to SelectPathEvent state events to sync the dropdown
    and CancelSelectPathEvent to revert the dropdown on cancellation.
    """

    def __init__(
        self,
        bus: EventBus,
        app_state: AppState,
        user_config: UserConfig | None = None,
        *,
        on_save_selected: OnSaveSelected | None = None,
        on_save_all: OnSaveAll | None = None,
    ) -> None:
        self._bus = bus
        self._app_state = app_state
        self._user_config = user_config
        self._current_folder: Path | None = None
        self._recent_menu: Optional[ui.menu] = None
        self._recent_menu_button: Optional[ui.button] = None
        self._menu_container: Optional[ui.element] = None
        self._choose_button: Optional[ui.button] = None
        self._open_file_button: Optional[ui.button] = None
        self._open_csv_button: Optional[ui.button] = None
        self._task_state: Optional[TaskStateChanged] = None
        self._suppress_path_selection_emit: bool = False
        
        # Save button callbacks
        self._on_save_selected = on_save_selected
        self._on_save_all = on_save_all
        
        # Save button UI elements
        self._save_selected_button: Optional[ui.button] = None
        self._save_all_button: Optional[ui.button] = None
        
        # Current file for save button state
        self._current_file: Optional[KymImage] = None
        
        # Subscribe to state and cancellation events
        bus.subscribe_state(SelectPathEvent, self._on_select_path_event)
        bus.subscribe(CancelSelectPathEvent, self._on_select_path_cancelled)
        
        # Subscribe to file selection and task state for save button states
        if on_save_selected is not None or on_save_all is not None:
            bus.subscribe_state(FileSelection, self._on_file_selection_changed)
            bus.subscribe_state(TaskStateChanged, self._on_task_state_changed)

    def _build_recent_menu_data(self) -> tuple[list[tuple[str, int]], list[str], list[str]]:
        """Build recent folders/files/CSVs data from UserConfig for menu building.
        
        Returns:
            Tuple of (folder_paths_with_depths, file_paths, csv_paths).
            These are the FULL paths used for event emission.
        """
        folder_paths: list[tuple[str, int]] = []
        file_paths: list[str] = []
        csv_paths: list[str] = []
        if self._user_config is not None:
            folder_paths = self._user_config.get_recent_folders()
            file_paths = self._user_config.get_recent_files()
            csv_paths = self._user_config.get_recent_csvs()
        return (folder_paths, file_paths, csv_paths)
    
    def _build_recent_menu_data_display(self) -> tuple[list[tuple[str, int]], list[str], list[str]]:
        """Build recent folders/files/CSVs display data from UserConfig for menu building.
        
        Returns:
            Tuple of (folder_paths_with_depths, file_paths, csv_paths).
            These are DISPLAY paths (using ~ notation) for menu labels.
        """
        folder_paths: list[tuple[str, int]] = []
        file_paths: list[str] = []
        csv_paths: list[str] = []
        if self._user_config is not None:
            folder_paths = self._user_config.get_recent_folders_display()
            file_paths = self._user_config.get_recent_files_display()
            csv_paths = self._user_config.get_recent_csvs_display()
        return (folder_paths, file_paths, csv_paths)

    def _on_recent_path_selected(self, new_path_selection: str, is_csv: bool = False) -> None:
        """Handle recent folder/file/CSV selection from menu item.
        
        Args:
            new_path_selection: The path selected from the menu.
            is_csv: True if this is a CSV file path.
        """
        if self._suppress_path_selection_emit:
            return
        
        logger.info(f'new_path_selection:{new_path_selection}')
        if self._app_state.folder and str(self._app_state.folder) == new_path_selection:
            logger.info(f'  -->> reject ... is the same as the current folder: {new_path_selection}')
            return
        
        # Check if path exists
        path_obj = Path(new_path_selection)
        if not path_obj.exists():
            # Show dialog and remove from config
            self._show_missing_path_dialog(new_path_selection)
            # Remove from UserConfig
            if self._user_config is not None:
                # Re-add to remove it (push_recent_path removes duplicates)
                # Actually, we need a better way - let's just rebuild the menu
                # For now, we'll let the next load clean it up
                pass
            return
        
        # Get depth for folder/file (CSV will be auto-detected by FolderController)
        if self._user_config is not None:
            depth = self._user_config.get_depth_for_folder(new_path_selection)
        else:
            depth = self._app_state.folder_depth

        # Emit event - FolderController will auto-detect CSV from path
        self._bus.emit(SelectPathEvent(
            new_path=new_path_selection,
            depth=depth,
            phase="intent",
        ))
    
    def _show_missing_path_dialog(self, path: str) -> None:
        """Show dialog when selected path doesn't exist."""
        with ui.dialog() as dialog, ui.card().classes("w-[520px]"):
            ui.label("Item does not exist").classes("text-lg font-semibold")
            ui.label(path).classes("text-sm break-all")
            with ui.row().classes("justify-end w-full"):
                ui.button("OK", on_click=dialog.close)
        dialog.open()
    
    def _on_clear_recent(self) -> None:
        """Clear all recent paths from UserConfig."""
        if self._user_config is not None:
            self._user_config.clear_recent_paths()
            self._user_config.save()
            # Rebuild menu to reflect cleared state
            safe_call(self._rebuild_menu_if_needed)
            ui.notify("Cleared recently opened items", type="info")
    
    def _calculate_depth_for_path(self, path_type: PathType) -> int | None:
        """Calculate depth for path selection based on path type.
        
        Args:
            path_type: Type of path selection (FOLDER, FILE, or CSV).
        
        Returns:
            Depth value for folders, or None for files/CSV (controller will use 0).
        """
        if path_type == PathType.FOLDER:
            return self._app_state.folder_depth
        else:
            # Files and CSV don't use depth (controller will use 0)
            return None

    async def _on_open_path(self, path_type: PathType, file_extension: Optional[str] = None) -> None:
        """Unified handler for opening folder, file, or CSV path selection.
        
        Args:
            path_type: Type of path selection (FOLDER, FILE, or CSV).
            file_extension: File extension for file/CSV dialogs. Defaults to ".tif" for FILE,
                ".csv" for CSV. Ignored for FOLDER.
        """
        # Validate native mode availability
        is_available, error_msg = _validate_native_mode_for_dialog(path_type)
        if not is_available:
            ui.notify(error_msg, type="warning")
            return
        
        # Determine file extension and dialog type
        if path_type == PathType.FOLDER:
            dialog_type = "folder"
            ext = None
        else:  # FILE or CSV
            dialog_type = "file"
            if file_extension is None:
                ext = ".csv" if path_type == PathType.CSV else ".tif"
            else:
                ext = file_extension
        
        try:
            initial = self._current_folder if self._current_folder is not None else Path.home()
            
            # Call _prompt_for_path with appropriate parameters
            if ext is not None:
                selected = await _prompt_for_path(initial, dialog_type=dialog_type, file_extension=ext)
            else:
                selected = await _prompt_for_path(initial, dialog_type=dialog_type)
            
            if selected:
                # Calculate depth for the path type
                depth = self._calculate_depth_for_path(path_type)
                
                # Emit event with consistent parameters (always include depth)
                self._bus.emit(SelectPathEvent(
                    new_path=str(selected),
                    depth=depth,
                    phase="intent",
                ))
                
                # Show success notification
                path_type_str = path_type.value.capitalize()
                ui.notify(f"{path_type_str} selected: {selected}", type="positive")
        except Exception as exc:
            logger.error(f"{path_type.value.capitalize()} selection failed: %s", exc, exc_info=True)
            ui.notify(f"Failed to select {path_type.value}: {exc}", type="negative")

    def render(self, *, initial_folder: Path | None = None) -> None:
        """Create the folder selector UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.

        This method is called on every page navigation. We always recreate UI
        elements rather than trying to detect if they're still valid, which is
        simpler and more reliable.
        
        Args:
            initial_folder: Initial folder path to use for file dialogs. If None,
                uses app_state.folder if available, otherwise Path.home().
        """
        if initial_folder is None:
            initial_folder = self._app_state.folder if self._app_state.folder else Path.home()
        self._current_folder = initial_folder

        self._recent_menu = None
        self._recent_menu_button = None
        self._choose_button = None
        self._open_file_button = None
        self._open_csv_button = None
        self._save_selected_button = None
        self._save_all_button = None

        with ui.row().classes("w-full items-center gap-2"):
            # Left side: existing controls
            
            # Button and menu container - button must be created first, then menu
            with ui.element("div").classes("inline-block") as menu_container:
                self._menu_container = menu_container
                # Create button first
                self._recent_menu_button = ui.button(
                    icon="menu",
                    on_click=lambda: self._recent_menu.open() if self._recent_menu else None,
                ).props("dense flat").classes("text-sm")
                # self._recent_menu_button.tooltip("Recently opened folders and files")
                
                # Then create menu (will be positioned relative to button)
                self._build_recent_menu()
                
                # Update button state based on available paths
                folder_paths, file_paths, csv_paths = self._build_recent_menu_data()
                if not folder_paths and not file_paths and not csv_paths:
                    self._recent_menu_button.disable()
            
            self._choose_button = ui.button("Open folder", on_click=lambda: self._on_open_path(PathType.FOLDER)).props("dense").classes("text-sm")
            self._open_file_button = ui.button("Open file", on_click=lambda: self._on_open_path(PathType.FILE)).props("dense").classes("text-sm")
            self._open_csv_button = ui.button("Open CSV", on_click=lambda: self._on_open_path(PathType.CSV)).props("dense").classes("text-sm")

            # Spacer to push save buttons to the right
            ui.element("div").classes("grow")
            
            # Right side: save buttons
            if self._on_save_selected is not None or self._on_save_all is not None:
                self._save_selected_button = ui.button(
                    "Save Selected",
                    on_click=self._on_save_selected_click,
                    icon="save"
                ).props("dense").classes("text-sm")
                self._save_all_button = ui.button(
                    "Save All",
                    on_click=self._on_save_all_click
                ).props("dense").classes("text-sm")
        self._update_controls_state()
        self._update_save_button_states()
        self.set_folder_from_state()
    
    def _build_recent_menu(self) -> None:
        """Build or rebuild the recent paths menu."""
        # Get display paths for menu labels (using ~ notation)
        folder_paths_display, file_paths_display, csv_paths_display = self._build_recent_menu_data_display()
        
        # Get full paths for event emission (used in callbacks)
        folder_paths_full, file_paths_full, csv_paths_full = self._build_recent_menu_data()
        
        # Get current paths from app state for comparison (use full paths)
        current_folder_path = str(self._app_state.folder) if self._app_state.folder else None

        # Build menu first (needed for button callback)
        with ui.menu() as menu:
            self._recent_menu = menu
            
            # Folders header
            # header_folders = ui.menu_item("Folders")
            # header_folders.disable()
            
            # Folder items - use display path for label, full path for callback
            for (display_path, _depth), (full_path, _) in zip(folder_paths_display, folder_paths_full):
                is_current = (current_folder_path == full_path)
                prefix = "✓ " if is_current else "  "
                ui.menu_item(
                    f"{prefix} {display_path}",
                    lambda p=full_path: self._on_recent_path_selected(p),
                )
            
            if folder_paths_display:
                ui.separator()
            
            # Files header
            # if file_paths_display:
            #     header_files = ui.menu_item("Files")
            #     header_files.disable()
            
            # File items - use display path for label, full path for callback
            for display_path, full_path in zip(file_paths_display, file_paths_full):
                is_current = (current_folder_path == full_path)
                prefix = "✓ " if is_current else "  "
                ui.menu_item(
                    f"{prefix} {display_path}",
                    lambda p=full_path: self._on_recent_path_selected(p),
                )
            
            if file_paths_display:
                ui.separator()
            
            # CSV items - use display path for label, full path for callback
            for display_path, full_path in zip(csv_paths_display, csv_paths_full):
                is_current = (current_folder_path == full_path)
                prefix = "✓ " if is_current else "  "
                ui.menu_item(
                    f"{prefix} {display_path}",
                    lambda p=full_path: self._on_recent_path_selected(p, is_csv=True),
                )
            
            if folder_paths_display or file_paths_display or csv_paths_display:
                ui.separator()
            
                # Clear option
                ui.menu_item("Clear Recently Opened …", self._on_clear_recent)
        
        # Button state will be updated by caller

    def set_task_state(self, task_state: TaskStateChanged) -> None:
        """Update view for task state changes."""
        safe_call(self._set_task_state_impl, task_state)


    def _set_task_state_impl(self, task_state: TaskStateChanged) -> None:
        """Internal implementation of set_task_state."""
        self._task_state = task_state
        self._update_controls_state()

    def _update_controls_state(self) -> None:
        """Enable/disable folder controls based on task running state."""
        running = self._task_state.running if self._task_state else False
        if self._recent_menu_button is not None:
            if running:
                self._recent_menu_button.disable()
            else:
                folder_paths, file_paths, csv_paths = self._build_recent_menu_data()
                if folder_paths or file_paths or csv_paths:
                    self._recent_menu_button.enable()
                else:
                    self._recent_menu_button.disable()
        if self._choose_button is not None:
            if running:
                self._choose_button.disable()
            else:
                self._choose_button.enable()
        if self._open_file_button is not None:
            if running:
                self._open_file_button.disable()
            else:
                self._open_file_button.enable()
        if self._open_csv_button is not None:
            if running:
                self._open_csv_button.disable()
            else:
                self._open_csv_button.enable()
    
    def _update_save_button_states(self) -> None:
        """Update save button states based on current file and task state."""
        if self._save_selected_button is None or self._save_all_button is None:
            return
        
        running = self._task_state.running if self._task_state else False
        
        # Disable buttons when task is running
        if running:
            self._save_selected_button.disable()
            self._save_all_button.disable()
        else:
            # Save Selected: enabled when file is selected (and not running)
            has_file = self._current_file is not None
            if has_file:
                self._save_selected_button.enable()
            else:
                self._save_selected_button.disable()
            
            # Save All: always enabled when not running (will check files in controller)
            self._save_all_button.enable()
    
    def _on_file_selection_changed(self, e: FileSelection) -> None:
        """Handle file selection change event for save button state."""
        self._current_file = e.file
        safe_call(self._update_save_button_states)
    
    def _on_task_state_changed(self, e: TaskStateChanged) -> None:
        """Handle task state change event for save button state."""
        if e.task_type == "home":
            self._task_state = e
            safe_call(self._update_save_button_states)
    
    def _on_save_selected_click(self) -> None:
        """Handle Save Selected button click."""
        if self._on_save_selected is not None:
            self._on_save_selected(
                SaveSelected(
                    phase="intent",
                )
            )
    
    def _on_save_all_click(self) -> None:
        """Handle Save All button click."""
        if self._on_save_all is not None:
            self._on_save_all(
                SaveAll(
                    phase="intent",
                )
            )

    def set_folder_from_state(self) -> None:
        """Update folder display to match AppState."""
        if self._app_state.folder:
            self._current_folder = self._app_state.folder
        elif self._current_folder is None:
            self._current_folder = Path.home()
        # Menu doesn't have selected state, so no need to sync
    
    def _on_select_path_event(self, e: SelectPathEvent) -> None:
        """Handle SelectPathEvent state event - rebuild menu with updated paths."""
        safe_call(self._rebuild_menu_if_needed)
        safe_call(self.set_folder_from_state)
    
    def _rebuild_menu_if_needed(self) -> None:
        """Rebuild the menu if it exists and paths have changed."""
        if self._menu_container is None or self._recent_menu_button is None:
            return
        
        # Close menu if open to prevent auto-opening
        try:
            if self._recent_menu:
                self._recent_menu.close()
        except Exception:
            pass
        
        # Rebuild menu (button stays, menu is recreated in same container)
        try:
            # Delete old menu element if it exists
            if self._recent_menu is not None:
                try:
                    # Remove the old menu from DOM
                    self._recent_menu.delete()
                except Exception:
                    pass
            
            # Recreate the menu in the SAME container context as the button
            # This is critical for proper positioning
            self._recent_menu = None
            with self._menu_container:
                self._build_recent_menu()
            
            # Update button callback to use new menu
            if self._recent_menu:
                self._recent_menu_button.on_click(lambda: self._recent_menu.open() if self._recent_menu else None)
            
            # Update button state
            folder_paths, file_paths, csv_paths = self._build_recent_menu_data()
            if not folder_paths and not file_paths and not csv_paths:
                self._recent_menu_button.disable()
            else:
                self._recent_menu_button.enable()
            self._update_controls_state()
        except Exception as exc:
            logger.error(f"Failed to rebuild menu: {exc}", exc_info=True)
    
    def _on_select_path_cancelled(self, e: CancelSelectPathEvent) -> None:
        """Handle CancelSelectPathEvent - menu doesn't have selected state."""
        # Menu doesn't have selected state, so no need to revert
        pass