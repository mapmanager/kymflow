# src/kymflow/gui_v2/views/folder_selector_view.py
# gpt 20260106: dev-simple folder selector; no auto-load; no OS dialogs

from __future__ import annotations

from pathlib import Path
from typing import Optional

from nicegui import ui

from kymflow.core.utils.logging import get_logger
from kymflow.gui.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_folder import FolderChosen

logger = get_logger(__name__)


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

        # Always reset UI element reference - NiceGUI will clean up old elements
        # This ensures we create fresh elements in the new container context
        self._folder_display = None

        with ui.row().classes("w-full items-center gap-2"):
            ui.button("Choose folder (disabled for now)", on_click=lambda: None).props("disable")
            ui.button("Reload", on_click=_emit)

            ui.label("Depth:").classes("ml-2")
            depth_input = ui.number(value=self._app_state.folder_depth, min=1, format="%d").classes("w-20")
            depth_input.bind_value(self._app_state, "folder_depth")

            self._folder_display = ui.label(f"Folder: {self._current_folder}")