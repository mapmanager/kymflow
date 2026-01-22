"""Controller for persisting file selection to browser storage.

This module provides a controller that saves file selections to NiceGUI's
per-client storage, allowing selections to be restored across page reloads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import app

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import FileSelection, SelectionOrigin

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
        - Stores single path string for selected file

    Attributes:
        _app_state: AppState instance (not directly used, but kept for consistency).
        _storage_key: Storage key for persisting selection.
    """

    def __init__(self, app_state: AppState, bus: EventBus, *, storage_key: str) -> None:
        """Initialize persistence controller.

        Subscribes to FileSelection (phase="state") events to save selections.

        Args:
            app_state: AppState instance (kept for consistency with other controllers).
            bus: EventBus instance to subscribe to.
            storage_key: Key to use in app.storage.user for persisting selection.
        """
        self._app_state: AppState = app_state
        self._storage_key: str = storage_key

        # Subscribe to state events, but filter by origin=FILE_TABLE (only persist user actions)
        bus.subscribe_state(FileSelection, self._on_file_selected)

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

    def _on_file_selected(self, e: FileSelection) -> None:
        """Handle FileSelection state event and persist selection.

        Saves the selected file path to storage, but only if the origin is
        FILE_TABLE (user selection), not RESTORE or EXTERNAL (programmatic).

        Args:
            e: FileSelection event (phase="state") containing the selected file/path and origin.
        """
        # Don't persist programmatic selections (restore, external updates)
        if e.origin in {SelectionOrigin.RESTORE, SelectionOrigin.EXTERNAL}:
            return

        # Use path from event, or derive from file
        path = e.path
        if path is None and e.file is not None and hasattr(e.file, "path"):
            path = str(e.file.path)

        if path:
            app.storage.user[self._storage_key] = path
            logger.info(f"stored selection {path!r} -> {self._storage_key}")
