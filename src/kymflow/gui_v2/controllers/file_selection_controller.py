# src/kymflow/gui_v2/controllers/file_selection_controller.py
from __future__ import annotations

from kymflow.gui.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import FileSelected, FilesSelected, SelectionOrigin


class FileSelectionController:
    """Apply file-table selection events to AppState.select_file()."""

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        self._app_state = app_state
        bus.subscribe(FileSelected, self._on_file_selected)
        bus.subscribe(FilesSelected, self._on_files_selected)

    def _on_file_selected(self, e: FileSelected) -> None:
        if e.origin != SelectionOrigin.FILE_TABLE:
            return

        if e.path is None:
            self._app_state.select_file(None, origin=None)
            return

        match = None
        for f in self._app_state.files:
            if str(f.path) == e.path:
                match = f
                break

        self._app_state.select_file(match, origin=None)

    def _on_files_selected(self, e: FilesSelected) -> None:
        # v2 still drives AppState with a single selected file (like v1).
        if not e.paths:
            self._app_state.select_file(None, origin=None)
            return
        self._on_file_selected(FileSelected(path=e.paths[0], origin=SelectionOrigin.FILE_TABLE))
