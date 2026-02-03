# src/kymflow/gui_v2/views/folder_selector_view.py
# gpt 20260106: dev-simple folder selector; no auto-load; no OS dialogs

from __future__ import annotations

from pathlib import Path
from typing import Optional

from nicegui import ui, app

from kymflow.core.utils.logging import get_logger
# from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_folder import SelectPathEvent, CancelSelectPathEvent
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
    """Folder selector UI that emits PathChosen.

    Dev behavior:
        - "Choose folder" disabled (no dialogs).
        - Reload emits PathChosen(current_folder).
        - Depth changes do NOT rescan automatically.
    """

    def __init__(self, bus: EventBus, app_state: AppState, user_config: UserConfig | None = None) -> None:
        self._bus = bus
        self._app_state = app_state
        self._user_config = user_config
        self._current_folder: Path = Path(".")
        # self._folder_display: Optional[ui.label] = None
        self._recent_ui_select: Optional[ui.select] = None
        self._choose_button: Optional[ui.button] = None
        self._open_file_button: Optional[ui.button] = None
        # self._reload_button: Optional[ui.button] = None  # DEPRECATED
        self._depth_input: Optional[ui.number] = None
        self._task_state: Optional[TaskStateChanged] = None
        
        # Subscribe to state and cancellation events
        bus.subscribe_state(SelectPathEvent, self._on_select_path_event)
        bus.subscribe(CancelSelectPathEvent, self._on_select_path_cancelled)

    def _on_recent_path_selected(self, new_path_selection:str) -> None:
        """Handle recent folder/file selection from ui.select dropdown.

        NiceGUI updates the select value *before* calling the callback. When available,
        use the event's previous value so we can reliably revert on cancel.
        
        Args:
            new_path_selection: The new path selection from the ui.select dropdown.
        """
        if self._recent_ui_select is None:
            return

        # Capture previous path for revert on cancel.
        # Prefer event.previous_value (the value before user changed the dropdown).
        # previous_path: str | None = getattr(e, "previous_value", None)
        # if previous_path is None:
        #     # Fallback: use what AppState thinks is loaded (folder), may be parent dir in file mode.
        #     previous_path = str(self._app_state.folder) if self._app_state.folder else None
        
        # Skip if already loaded
        # current_folder: When a folder is loaded, this is the folder path.
        #                 When a file is loaded, this is the parent directory.
        # current_folder: Path = self._app_state.folder
        # # current_kym_image: The currently selected file in the file table view.
        # #                    Needed to skip when user selects the same file again
        # #                    (since current_folder would only match the parent directory).
        # current_kym_image: Optional[KymImage] = self._app_state.selected_file

        # logger.debug(f"selected_path: {selected_path}")
        # logger.debug(f"current_folder: {current_folder}")
        # logger.debug(f"current_kym_image: {current_kym_image}")

        # if (current_folder and str(current_folder) == str(new_path)) or \
        #    (current_kym_image and str(current_kym_image.path) == str(new_path)):
        #     logger.debug(f"Skipping recent selection - selectedpath already loaded: {new_path}")
        #     return
        
        # Note: Path existence check is handled by FolderController, which will emit
        # PathChosenCancelled if the path doesn't exist, allowing the view to revert the dropdown.
        
        # Get depth from config (will be 0 for files, actual depth for folders)
        # The FolderController will handle file vs folder distinction and depth updates
        # depth = self._app_state.folder_depth
        # if self._user_config is not None:
        #     depth = self._user_config.get_depth_for_folder(new_path_selection)
        
        # get the depth from ui
        depth = self._depth_input.value if self._depth_input is not None else None

        # For files, depth will be ignored by controller; for folders, controller uses it
        # FolderController handles all file vs folder logic, so we just emit the path and depth
        selectedPathEvent = SelectPathEvent(
            new_path=new_path_selection,
            depth=depth,
            phase="intent",
        )
        logger.info(f'selectedPathEvent:{selectedPathEvent}')

        self._bus.emit(selectedPathEvent)

    async def _on_choose_folder(self) -> None:
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
                self._bus.emit(SelectPathEvent(
                    new_path=str(selected),
                    depth=None,
                    phase="intent",
                ))
                logger.info("Folder selected: %s", selected)
                ui.notify(f"Folder selected: {selected}", type="positive")
        except Exception as exc:
            logger.error("Folder selection failed: %s", exc, exc_info=True)
            ui.notify(f"Failed to select folder: {exc}", type="negative")

    async def _on_open_file(self) -> None:
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
                self._bus.emit(SelectPathEvent(
                    new_path=str(Path(selected)),
                    phase="intent",
                ))
                logger.info("File selected: %s", selected)
                ui.notify(f"File selected: {selected}", type="positive")
            # If selected is None, user cancelled - no notification needed
        except Exception as exc:
            logger.error("File selection failed: %s", exc, exc_info=True)
            ui.notify(f"Failed to select file: {exc}", type="negative")

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
        #     logger.info("FolderSelectorView emit PathChosen(%s)", self._current_folder)
        #     self._bus.emit(PathChosen(new_path=str(self._current_folder), phase="intent"))

        # Always reset UI element reference - NiceGUI will clean up old elements
        # This ensures we create fresh elements in the new container context
        # self._folder_display = None
        self._recent_ui_select = None
        self._choose_button = None
        self._open_file_button = None
        # self._reload_button = None  # DEPRECATED
        self._depth_input = None

        # Build recent folders/files items
        recent_options: dict[str, str] = {}
        # if self._user_config is not None:
        if 1:
            _recent_paths = self._user_config.get_recent_folders()  # Now includes files
            for _one_path, _depth in _recent_paths:
                path_obj = Path(_one_path)
                if path_obj.is_file():
                    # Add file icon indicator (Material Design icon)
                    display_item = f"📄 {_one_path}"
                    # display = path
                else:
                    # Add folder icon indicator (Material Design icon)
                    display_item = f"📂 {_one_path}"
                    # display = path
                recent_options[_one_path] = display_item

        # logger.warning(f'recent_options:')
        # for _recentKey, _recentValue in recent_options.items():
        #     logger.warning(f'  _recentKey: {_recentKey}')
        #     logger.warning(f'  _recentValue: {_recentValue}')

        _last_path, _lastDepth = self._user_config.get_last_folder()

        with ui.row().classes("w-full items-center gap-2"):
            # Recent folders dropdown
            if recent_options:
                self._recent_ui_select = ui.select(
                    options=recent_options,
                    label="Recent",
                    value=_last_path,  # initial value
                    on_change=lambda e: self._on_recent_path_selected(e.value),
                ).classes("min-w-64")
            else:
                logger.debug('xxx empty ui.select')
                self._recent_ui_select = ui.select(
                    options={},
                    label="Recent",
                ).classes("min-w-64")
                self._recent_ui_select.disable()
                self._recent_ui_select.props("placeholder=No recent folders/files")
            
            # Always enable the button - check happens dynamically when clicked
            # This avoids timing issues with pywebview window initialization
            self._choose_button = ui.button("Open folder", on_click=self._on_choose_folder).props("dense").classes("text-sm")
            self._open_file_button = ui.button("Open file", on_click=self._on_open_file).props("dense").classes("text-sm")
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
        if self._recent_ui_select is not None:
            if running:
                self._recent_ui_select.disable()
            else:
                options = getattr(self._recent_ui_select, "options", None)
                if options:
                    self._recent_ui_select.enable()
                else:
                    self._recent_ui_select.disable()
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
        if self._recent_ui_select is not None:
            options = getattr(self._recent_ui_select, "options", None)
            if options and str(self._current_folder) in options:
                # Only set value if it's different to avoid triggering on_change callback
                # This prevents double-loading when syncing UI after folder load
                current_value = getattr(self._recent_ui_select, "value", None)
                if current_value != str(self._current_folder):
                    self._recent_ui_select.set_value(str(self._current_folder))
    
    def _on_select_path_event(self, e: SelectPathEvent) -> None:
        """Handle PathChosen state event - sync dropdown to confirmed path."""
        # State event means path was successfully loaded
        # Sync dropdown to match AppState (set_folder_from_state handles this)
        safe_call(self.set_folder_from_state)
    
    def _on_select_path_cancelled(self, e: CancelSelectPathEvent) -> None:
        """Handle PathChosenCancelled event - revert dropdown to previous path."""
        if self._recent_ui_select is None:
            return
        
        # Revert dropdown to previous path
        previous_path = e.previous_path
        if previous_path:
            options = getattr(self._recent_ui_select, "options", None)
            if options and previous_path in options:
                # Only set value if it's different to avoid triggering on_change callback
                current_value = getattr(self._recent_ui_select, "value", None)
                if current_value != previous_path:
                    self._recent_ui_select.set_value(previous_path)
                    logger.debug(f"Reverted dropdown to previous path: {previous_path}")