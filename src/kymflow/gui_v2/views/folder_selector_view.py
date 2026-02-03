"""Folder selector view for path selection (folder or file).

This module provides the UI component for selecting folders or files,
emitting SelectPathEvent intent events when paths are selected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from nicegui import ui, app

from kymflow.core.utils.logging import get_logger
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
    """Folder selector UI that emits SelectPathEvent.

    This view provides UI controls for selecting folders or files:
    - Recent paths dropdown (from UserConfig)
    - "Open folder" button (native file dialog)
    - "Open file" button (native file dialog)
    - Depth input (for folder scanning)

    The view subscribes to SelectPathEvent state events to sync the dropdown
    and CancelSelectPathEvent to revert the dropdown on cancellation.
    """

    def __init__(self, bus: EventBus, app_state: AppState, user_config: UserConfig | None = None) -> None:
        self._bus = bus
        self._app_state = app_state
        self._user_config = user_config
        self._current_folder: Path | None = None
        self._recent_ui_select: Optional[ui.select] = None
        self._choose_button: Optional[ui.button] = None
        self._open_file_button: Optional[ui.button] = None
        self._depth_input: Optional[ui.number] = None
        self._task_state: Optional[TaskStateChanged] = None
        self._suppress_path_selection_emit: bool = False
        
        # Subscribe to state and cancellation events
        bus.subscribe_state(SelectPathEvent, self._on_select_path_event)
        bus.subscribe(CancelSelectPathEvent, self._on_select_path_cancelled)

    def _build_recent_options(self) -> dict[str, str]:
        """Build recent folders/files options dict from UserConfig.
        
        Returns:
            Dictionary mapping path strings to display strings (with icons).
        """
        recent_options: dict[str, str] = {}
        if self._user_config is not None:
            recent_items = self._user_config.get_recent_folders()  # Now includes files
            for path, _depth in recent_items:
                path_obj = Path(path)
                if path_obj.is_file():
                    display_item = f"📄 {path}"
                else:
                    display_item = f"📂 {path}"
                recent_options[path] = display_item
        return recent_options

    def _on_recent_path_selected(self, new_path_selection: str) -> None:
        """Handle recent folder/file selection from ui.select dropdown.
        
        Args:
            new_path_selection: The new path selection from the ui.select dropdown.
        """
        if self._recent_ui_select is None:
            return
        
        if self._suppress_path_selection_emit:
            return
        
        if self._app_state.folder and str(self._app_state.folder) == new_path_selection:
            return
        
        if self._user_config is not None:
            depth = self._user_config.get_depth_for_folder(new_path_selection)
        else:
            depth = self._app_state.folder_depth

        self._bus.emit(SelectPathEvent(
            new_path=new_path_selection,
            depth=depth,
            phase="intent",
        ))

    async def _on_choose_folder(self) -> None:
        """Handle folder selection button click."""
        # Check if pywebview module is available at all
        try:
            import webview  # type: ignore
        except ImportError:
            msg = "Folder selection requires native mode with pywebview. Please restart with KYMFLOW_GUI_NATIVE=1"
            ui.notify(msg, type="warning")
            return

        native = getattr(app, "native", None)
        main_window = getattr(native, "main_window", None) if native else None
        
        windows = getattr(webview, "windows", None)
        num_windows = len(windows) if windows else 0
        
        if main_window is None and (not windows or num_windows == 0):
            msg = "Native window not available. Please ensure you're running with KYMFLOW_GUI_NATIVE=1"
            ui.notify(msg, type="warning")
            return

        try:
            initial = self._current_folder if self._current_folder is not None else Path.home()
            selected = await _prompt_for_directory_pywebview(initial)
            if selected:
                depth = self._depth_input.value if self._depth_input is not None else self._app_state.folder_depth
                self._bus.emit(SelectPathEvent(
                    new_path=str(selected),
                    depth=depth,
                    phase="intent",
                ))
                ui.notify(f"Folder selected: {selected}", type="positive")
        except Exception as exc:
            logger.error("Folder selection failed: %s", exc, exc_info=True)
            ui.notify(f"Failed to select folder: {exc}", type="negative")

    async def _on_open_file(self) -> None:
        """Handle file selection button click."""
        # Check if pywebview module is available at all
        try:
            import webview  # type: ignore
        except ImportError:
            msg = "File selection requires native mode with pywebview. Please restart with KYMFLOW_GUI_NATIVE=1"
            ui.notify(msg, type="warning")
            return

        native = getattr(app, "native", None)
        main_window = getattr(native, "main_window", None) if native else None
        
        windows = getattr(webview, "windows", None)
        num_windows = len(windows) if windows else 0
        
        if main_window is None and (not windows or num_windows == 0):
            msg = "Native window not available. Please ensure you're running with KYMFLOW_GUI_NATIVE=1"
            ui.notify(msg, type="warning")
            return

        try:
            initial = self._current_folder if self._current_folder is not None else Path.home()
            selected = await _prompt_for_file_pywebview(initial)
            if selected:
                self._bus.emit(SelectPathEvent(
                    new_path=str(Path(selected)),
                    phase="intent",
                ))
                ui.notify(f"File selected: {selected}", type="positive")
        except Exception as exc:
            logger.error("File selection failed: %s", exc, exc_info=True)
            ui.notify(f"Failed to select file: {exc}", type="negative")

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

        self._recent_ui_select = None
        self._choose_button = None
        self._open_file_button = None
        self._depth_input = None

        recent_options = self._build_recent_options()

        _last_path, _lastDepth = self._user_config.get_last_folder() if self._user_config else (None, None)
        initial_value = _last_path if (_last_path and _last_path in recent_options) else None

        with ui.row().classes("w-full items-center gap-2"):
            # Recent folders dropdown
            if recent_options:
                self._recent_ui_select = ui.select(
                    options=recent_options,
                    label="Recent",
                    value=initial_value,  # Only set if path is in options
                    on_change=lambda e: self._on_recent_path_selected(e.value),
                ).classes("min-w-64")
            else:
                self._recent_ui_select = ui.select(
                    options={},
                    label="Recent",
                ).classes("min-w-64")
                self._recent_ui_select.disable()
                self._recent_ui_select.props("placeholder=No recent folders/files")
            
            self._choose_button = ui.button("Open folder", on_click=self._on_choose_folder).props("dense").classes("text-sm")
            self._open_file_button = ui.button("Open file", on_click=self._on_open_file).props("dense").classes("text-sm")

            ui.label("Depth:").classes("ml-2")
            self._depth_input = ui.number(value=self._app_state.folder_depth, min=1, format="%d").classes("w-10")
            self._depth_input.bind_value(self._app_state, "folder_depth")
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
        if self._depth_input is not None:
            if running:
                self._depth_input.disable()
            else:
                self._depth_input.enable()

    def set_folder_from_state(self) -> None:
        """Update folder display to match AppState."""
        if self._app_state.folder:
            self._current_folder = self._app_state.folder
        elif self._current_folder is None:
            self._current_folder = Path.home()
        if self._recent_ui_select is not None:
            options = getattr(self._recent_ui_select, "options", None)
            if options and str(self._current_folder) in options:
                current_value = getattr(self._recent_ui_select, "value", None)
                if current_value != str(self._current_folder):
                    self._suppress_path_selection_emit = True
                    try:
                        self._recent_ui_select.set_value(str(self._current_folder))
                    finally:
                        self._suppress_path_selection_emit = False
    
    def _on_select_path_event(self, e: SelectPathEvent) -> None:
        """Handle SelectPathEvent state event - sync dropdown to confirmed path."""
        if self._recent_ui_select is not None:
            recent_options = self._build_recent_options()
            if recent_options:
                self._recent_ui_select.set_options(recent_options)
        
        safe_call(self.set_folder_from_state)
    
    def _on_select_path_cancelled(self, e: CancelSelectPathEvent) -> None:
        """Handle CancelSelectPathEvent - revert dropdown to previous path."""
        if self._recent_ui_select is None:
            return
        
        previous_path = e.previous_path
        if previous_path:
            options = getattr(self._recent_ui_select, "options", None)
            if options and previous_path in options:
                current_value = getattr(self._recent_ui_select, "value", None)
                if current_value != previous_path:
                    self._suppress_path_selection_emit = True
                    try:
                        self._recent_ui_select.set_value(previous_path)
                    finally:
                        self._suppress_path_selection_emit = False