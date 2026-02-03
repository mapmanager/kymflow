# src/kymflow/gui_v2/views/folder_selector_view.py
# gpt 20260106: dev-simple folder selector; no auto-load; no OS dialogs

from __future__ import annotations

from pathlib import Path
from typing import Optional

from nicegui import ui, app

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_folder import FolderChosen
from kymflow.gui_v2.views.folder_picker import _prompt_for_directory_pywebview, _prompt_for_file_pywebview
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.gui_v2.client_utils import safe_call
from kymflow.core.user_config import UserConfig

logger = get_logger(__name__)


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


class FolderSelectorView:
    """Folder selector UI that emits FolderChosen.

    Dev behavior:
        - "Choose folder" disabled (no dialogs).
        - Reload emits FolderChosen(current_folder).
        - Depth changes do NOT rescan automatically.
    """

    def __init__(self, bus: EventBus, app_state: AppState, user_config: UserConfig | None = None) -> None:
        self._bus = bus
        self._app_state = app_state
        self._user_config = user_config
        self._current_folder: Path = Path(".")
        # self._folder_display: Optional[ui.label] = None
        self._recent_select: Optional[ui.select] = None
        self._choose_button: Optional[ui.button] = None
        self._open_file_button: Optional[ui.button] = None
        # self._reload_button: Optional[ui.button] = None  # DEPRECATED
        self._depth_input: Optional[ui.number] = None
        self._task_state: Optional[TaskStateChanged] = None

    def render(self, *, initial_folder: Path) -> None:
        """Create the folder selector UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.

        This method is called on every page navigation. We always recreate UI
        elements rather than trying to detect if they're still valid, which is
        simpler and more reliable.
        """
        self._current_folder = initial_folder

        # DEPRECATED: Reload button functionality
        # def _emit() -> None:
        #     logger.info("FolderSelectorView emit FolderChosen(%s)", self._current_folder)
        #     self._bus.emit(FolderChosen(folder=str(self._current_folder)))

        async def _choose_folder() -> None:
            """Handle folder selection button click."""
            # Check if pywebview module is available at all
            try:
                import webview  # type: ignore
            except ImportError as exc:
                msg = "Folder selection requires native mode with pywebview. Please restart with KYMFLOW_GUI_NATIVE=1"
                logger.warning("pywebview not available: %s", exc)
                ui.notify(msg, type="warning")
                return

            # Check for native mode using NiceGUI's app.native approach
            # This is more reliable than checking webview.windows directly
            native = getattr(app, "native", None)
            main_window = getattr(native, "main_window", None) if native else None
            
            # Also check webview.windows as fallback
            windows = getattr(webview, "windows", None)
            num_windows = len(windows) if windows else 0
            
            logger.debug(
                "Folder selection check: native=%s, main_window=%s, webview.windows=%s (len=%s)",
                native is not None,
                main_window is not None,
                windows is not None,
                num_windows,
            )

            # If neither method shows a window, show error
            if main_window is None and (not windows or num_windows == 0):
                msg = "Native window not available. Please ensure you're running with KYMFLOW_GUI_NATIVE=1"
                logger.warning(
                    "Native window not available: app.native.main_window=%s, webview.windows=%s",
                    main_window,
                    num_windows,
                )
                ui.notify(msg, type="warning")
                return

            try:
                # Use pywebview implementation (async)
                selected = await _prompt_for_directory_pywebview(self._current_folder)
                if selected:
                    # Emit event (label updates after load)
                    self._bus.emit(FolderChosen(folder=str(Path(selected))))
                    logger.info("Folder selected: %s", selected)
                    ui.notify(f"Folder selected: {selected}", type="positive")
                # If selected is None, user cancelled - no notification needed
            except Exception as exc:
                logger.error("Folder selection failed: %s", exc, exc_info=True)
                ui.notify(f"Failed to select folder: {exc}", type="negative")

        async def _open_file() -> None:
            """Handle file selection button click."""
            # Check if pywebview module is available at all
            try:
                import webview  # type: ignore
            except ImportError as exc:
                msg = "File selection requires native mode with pywebview. Please restart with KYMFLOW_GUI_NATIVE=1"
                logger.warning("pywebview not available: %s", exc)
                ui.notify(msg, type="warning")
                return

            # Check for native mode using NiceGUI's app.native approach
            # This is more reliable than checking webview.windows directly
            native = getattr(app, "native", None)
            main_window = getattr(native, "main_window", None) if native else None
            
            # Also check webview.windows as fallback
            windows = getattr(webview, "windows", None)
            num_windows = len(windows) if windows else 0
            
            logger.debug(
                "File selection check: native=%s, main_window=%s, webview.windows=%s (len=%s)",
                native is not None,
                main_window is not None,
                windows is not None,
                num_windows,
            )

            # If neither method shows a window, show error
            if main_window is None and (not windows or num_windows == 0):
                msg = "Native window not available. Please ensure you're running with KYMFLOW_GUI_NATIVE=1"
                logger.warning(
                    "Native window not available: app.native.main_window=%s, webview.windows=%s",
                    main_window,
                    num_windows,
                )
                ui.notify(msg, type="warning")
                return

            try:
                # Use pywebview implementation (async)
                selected = await _prompt_for_file_pywebview(self._current_folder)
                if selected:
                    # Emit event with depth=0 (will be ignored for files)
                    self._bus.emit(FolderChosen(folder=str(Path(selected)), depth=0))
                    logger.info("File selected: %s", selected)
                    ui.notify(f"File selected: {selected}", type="positive")
                # If selected is None, user cancelled - no notification needed
            except Exception as exc:
                logger.error("File selection failed: %s", exc, exc_info=True)
                ui.notify(f"Failed to select file: {exc}", type="negative")

        def _on_recent_folder_selected() -> None:
            """Handle recent folder/file selection from dropdown."""
            if self._recent_select is None:
                return
            
            selected_path = self._recent_select.value
            if not selected_path:
                return
            
            path = Path(selected_path)
            
            # Skip if already loaded
            current_folder = self._app_state.folder
            current_file = self._app_state.selected_file
            if (current_folder and str(current_folder) == str(path)) or \
               (current_file and str(current_file.path) == str(path)):
                logger.debug(f"Skipping recent selection - path already loaded: {selected_path}")
                return
            
            if not path.exists():
                # Updated: generic message for both files and folders
                ui.notify(f"Path no longer exists: {selected_path}", type="warning")
                return
            
            # Simplified: always get depth from config (will be 0 for files, actual depth for folders)
            # depth will be ignored by load_folder() for files
            depth = self._app_state.folder_depth
            if self._user_config is not None:
                depth = self._user_config.get_depth_for_folder(selected_path)
            
            # For files, don't update folder_depth (depth input won't update)
            # For folders, update folder_depth so depth input reflects the selected folder's depth
            if path.is_file():
                # File: emit with depth=0, don't update folder_depth
                logger.info(f"Recent file selected: {selected_path}")
                self._bus.emit(FolderChosen(folder=selected_path, depth=0))
            else:
                # Folder: update folder_depth and emit with depth
                if depth != self._app_state.folder_depth:
                    self._app_state.folder_depth = depth
                logger.info(f"Recent folder selected: {selected_path} (depth={depth})")
                self._bus.emit(FolderChosen(folder=selected_path, depth=depth))

        # Always reset UI element reference - NiceGUI will clean up old elements
        # This ensures we create fresh elements in the new container context
        # self._folder_display = None
        self._recent_select = None
        self._choose_button = None
        self._open_file_button = None
        # self._reload_button = None  # DEPRECATED
        self._depth_input = None

        # Build recent folders/files options (now includes both)
        recent_options: dict[str, str] = {}
        if self._user_config is not None:
            recent_items = self._user_config.get_recent_folders()  # Now includes files
            for path, _depth in recent_items:
                path_obj = Path(path)
                if path_obj.is_file():
                    # Add file icon indicator (Material Design icon)
                    display = f"📄 {path}"
                else:
                    # Add folder icon indicator (Material Design icon)
                    display = f"📂 {path}"
                recent_options[path] = display

        with ui.row().classes("w-full items-center gap-2"):
            # Recent folders dropdown
            if recent_options:
                self._recent_select = ui.select(
                    options=recent_options,
                    label="Recent",
                    on_change=_on_recent_folder_selected,
                ).classes("min-w-64")
            else:
                self._recent_select = ui.select(
                    options={},
                    label="Recent",
                ).classes("min-w-64")
                self._recent_select.disable()
                self._recent_select.props("placeholder=No recent folders/files")
            
            # Always enable the button - check happens dynamically when clicked
            # This avoids timing issues with pywebview window initialization
            self._choose_button = ui.button("Open folder", on_click=_choose_folder).props("dense").classes("text-sm")
            self._open_file_button = ui.button("Open file", on_click=_open_file).props("dense").classes("text-sm")
            # DEPRECATED: Reload button
            # self._reload_button = ui.button("Reload", on_click=_emit).props("dense").classes("text-sm")

            ui.label("Depth:").classes("ml-2")
            self._depth_input = ui.number(value=self._app_state.folder_depth, min=1, format="%d").classes("w-10")
            self._depth_input.bind_value(self._app_state, "folder_depth")

            # self._folder_display = ui.label(f"Folder: {self._current_folder}")
        self._update_controls_state()
        self.set_folder_from_state()

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
        if self._recent_select is not None:
            if running:
                self._recent_select.disable()
            else:
                options = getattr(self._recent_select, "options", None)
                if options:
                    self._recent_select.enable()
                else:
                    self._recent_select.disable()
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
        # DEPRECATED: Reload button state management
        # if self._reload_button is not None:
        #     if running:
        #         self._reload_button.disable()
        #     else:
        #         self._reload_button.enable()
        if self._depth_input is not None:
            if running:
                self._depth_input.disable()
            else:
                self._depth_input.enable()

    def set_folder_from_state(self) -> None:
        """Update folder display to match AppState."""
        folder = self._app_state.folder or self._current_folder
        self._current_folder = folder
        # if self._folder_display is not None:
        #     self._folder_display.set_text(f"Folder: {self._current_folder}")
        if self._recent_select is not None:
            options = getattr(self._recent_select, "options", None)
            if options and str(self._current_folder) in options:
                # Only set value if it's different to avoid triggering on_change callback
                # This prevents double-loading when syncing UI after folder load
                current_value = getattr(self._recent_select, "value", None)
                if current_value != str(self._current_folder):
                    self._recent_select.set_value(str(self._current_folder))