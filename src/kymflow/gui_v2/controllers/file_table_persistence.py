# src/kymflow/gui_v2/controllers/file_table_persistence.py
from __future__ import annotations

from nicegui import app

from kymflow.gui.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import FileSelected, FilesSelected, SelectionOrigin
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


class FileTablePersistenceController:
    """Persist file-table selection in browser storage.

    This matches your current desktop-replacement use case:
        - single web client
        - no login
        - persist "last selection" across refreshes
    """

    def __init__(self, app_state: AppState, bus: EventBus, *, storage_key: str) -> None:
        self._app_state = app_state
        self._storage_key = storage_key

        bus.subscribe(FileSelected, self._on_file_selected)
        bus.subscribe(FilesSelected, self._on_files_selected)

    def restore_selection(self) -> list[str]:
        """Restore selected path(s) from NiceGUI user storage."""
        stored = app.storage.user.get(self._storage_key)
        if stored is None:
            return []
        if isinstance(stored, list):
            return [str(p) for p in stored]
        return [str(stored)]

    def _on_file_selected(self, e: FileSelected) -> None:
        if e.origin in {SelectionOrigin.RESTORE, SelectionOrigin.EXTERNAL}:
            return
        app.storage.user[self._storage_key] = e.path
        logger.info(f"stored selection {e.path!r} -> {self._storage_key}")

    def _on_files_selected(self, e: FilesSelected) -> None:
        if e.origin in {SelectionOrigin.RESTORE, SelectionOrigin.EXTERNAL}:
            return
        app.storage.user[self._storage_key] = list(e.paths)
        logger.info(f"stored selection {len(e.paths)} rows -> {self._storage_key}")
