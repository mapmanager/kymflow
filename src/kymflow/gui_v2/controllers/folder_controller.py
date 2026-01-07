# src/kymflow/gui_v2/controllers/folder_controller.py
from __future__ import annotations

from pathlib import Path

from kymflow.gui.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_folder import FolderChosen


class FolderController:
    """Controller that applies FolderChosen events to AppState.load_folder()."""

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        self._app_state = app_state
        bus.subscribe(FolderChosen, self._on_folder_chosen)

    def _on_folder_chosen(self, e: FolderChosen) -> None:
        self._app_state.load_folder(Path(e.folder))
