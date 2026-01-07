"""Controller for persisting file selection to browser storage.

This module provides a controller that saves file selections to NiceGUI's
per-client storage, allowing selections to be restored across page reloads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import app

from kymflow.core.utils.logging import get_logger
from kymflow.gui.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import FileSelected, FilesSelected, SelectionOrigin

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class FileTablePersistenceController:
    """Persist file selection to browser storage.

    This controller subscribes to file selection events and saves the selected
    file path(s) to NiceGUI's per-client storage. Selections can be restored
    on page reload using restore_selection().

    Storage:
        - Uses app.storage.user (per-client, persists across page reloads)
        - Stores single path string for single selection
        - Stores list of paths for multi-selection

    Attributes:
        _app_state: AppState instance (not directly used, but kept for consistency).
        _storage_key: Storage key for persisting selection.
    """

    def __init__(self, app_state: AppState, bus: EventBus, *, storage_key: str) -> None:
        """Initialize persistence controller.

        Subscribes to FileSelected and FilesSelected events to save selections.

        Args:
            app_state: AppState instance (kept for consistency with other controllers).
            bus: EventBus instance to subscribe to.
            storage_key: Key to use in app.storage.user for persisting selection.
        """
        self._app_state: AppState = app_state
        self._storage_key: str = storage_key

        bus.subscribe(FileSelected, self._on_file_selected)
        bus.subscribe(FilesSelected, self._on_files_selected)

    def restore_selection(self) -> list[str]:
        """Restore selected file path(s) from browser storage.

        Reads the stored selection from NiceGUI's per-client storage and
        returns it as a list of paths. Returns empty list if no selection
        was stored.

        Returns:
            List of file paths that were previously selected, or empty list.
        """
        stored = app.storage.user.get(self._storage_key)
        if stored is None:
            return []
        if isinstance(stored, list):
            return [str(p) for p in stored]
        return [str(stored)]

    def _on_file_selected(self, e: FileSelected) -> None:
        """Handle FileSelected event and persist selection.

        Saves the selected file path to storage, but only if the origin is
        FILE_TABLE (user selection), not RESTORE or EXTERNAL (programmatic).

        Args:
            e: FileSelected event containing the selected path and origin.
        """
        # Don't persist programmatic selections (restore, external updates)
        if e.origin in {SelectionOrigin.RESTORE, SelectionOrigin.EXTERNAL}:
            return

        app.storage.user[self._storage_key] = e.path
        logger.info(f"stored selection {e.path!r} -> {self._storage_key}")

    def _on_files_selected(self, e: FilesSelected) -> None:
        """Handle FilesSelected event and persist selection.

        Saves the selected file paths to storage, but only if the origin is
        FILE_TABLE (user selection), not RESTORE or EXTERNAL (programmatic).

        Args:
            e: FilesSelected event containing the selected paths and origin.
        """
        # Don't persist programmatic selections (restore, external updates)
        if e.origin in {SelectionOrigin.RESTORE, SelectionOrigin.EXTERNAL}:
            return

        app.storage.user[self._storage_key] = list(e.paths)
        logger.info(f"stored selection {len(e.paths)} rows -> {self._storage_key}")
