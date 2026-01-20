# src/kymflow/gui_v2/views/folder_selector_view.py
# gpt 20260106: dev-simple folder selector; no auto-load; no OS dialogs

from __future__ import annotations

from pathlib import Path
from typing import Optional

from nicegui import ui, app

from kymflow.core.utils.logging import get_logger
from kymflow.gui.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_folder import FolderChosen
from kymflow.gui_v2.views.folder_picker import _prompt_for_directory_pywebview

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

    def __init__(self, bus: EventBus, app_state: AppState) -> None:
        self._bus = bus
        self._app_state = app_state
        self._current_folder: Path = Path(".")
        self._folder_display: Optional[ui.label] = None

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

        def _emit() -> None:
            logger.info("FolderSelectorView emit FolderChosen(%s)", self._current_folder)
            self._bus.emit(FolderChosen(folder=str(self._current_folder)))
            if self._folder_display is not None:
                self._folder_display.set_text(f"Folder: {self._current_folder}")

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
                    # Update and emit event
                    self._current_folder = Path(selected)
                    self._bus.emit(FolderChosen(folder=str(self._current_folder)))
                    if self._folder_display is not None:
                        self._folder_display.set_text(f"Folder: {self._current_folder}")
                    logger.info("Folder selected: %s", self._current_folder)
                    ui.notify(f"Folder selected: {self._current_folder}", type="positive")
                # If selected is None, user cancelled - no notification needed
            except Exception as exc:
                logger.error("Folder selection failed: %s", exc, exc_info=True)
                ui.notify(f"Failed to select folder: {exc}", type="negative")

        # Always reset UI element reference - NiceGUI will clean up old elements
        # This ensures we create fresh elements in the new container context
        self._folder_display = None

        with ui.row().classes("w-full items-center gap-2"):
            # Always enable the button - check happens dynamically when clicked
            # This avoids timing issues with pywebview window initialization
            ui.button("Choose folder", on_click=_choose_folder)
            ui.button("Reload", on_click=_emit)

            ui.label("Depth:").classes("ml-2")
            depth_input = ui.number(value=self._app_state.folder_depth, min=1, format="%d").classes("w-20")
            depth_input.bind_value(self._app_state, "folder_depth")

            self._folder_display = ui.label(f"Folder: {self._current_folder}")