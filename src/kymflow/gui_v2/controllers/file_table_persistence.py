"""Controller for persisting file selection across reconnects.

Persists the selected file path to :class:`~kymflow.gui_v2.app_config.AppConfig`
on disk (single source for native and web). Restores via ``restore_selection()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.app_config import AppConfig
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import FileSelection, SelectionOrigin

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class FileTablePersistenceController:
    """Persist file selection to AppConfig on disk.

    This controller subscribes to file selection events and saves the selected
    file path. Selections can be restored on page reload using restore_selection().

    Storage:
        - Uses ``AppConfig.last_selected_file_path`` (persisted JSON)

    Attributes:
        _app_state: AppState instance (kept for consistency with other controllers).
        _app_config: AppConfig instance for read/write.
    """

    def __init__(self, app_state: AppState, bus: EventBus, *, app_config: AppConfig) -> None:
        """Initialize persistence controller.

        Subscribes to FileSelection (phase="state") events to save selections.

        Args:
            app_state: AppState instance (kept for consistency with other controllers).
            bus: EventBus instance to subscribe to.
            app_config: AppConfig instance for disk-backed selection path.
        """
        self._app_state: AppState = app_state
        self._app_config: AppConfig = app_config

        bus.subscribe_state(FileSelection, self._on_file_selected)

    def restore_selection(self) -> list[str]:
        """Restore selected file path(s) from AppConfig.

        Returns:
            List of file paths that were previously selected, or empty list.
        """
        p = self._app_config.get_last_selected_file_path()
        if not p:
            return []
        return [p]

    def _on_file_selected(self, e: FileSelection) -> None:
        """Handle FileSelection state event and persist selection.

        Saves the selected file path to AppConfig, but only if the origin is
        FILE_TABLE (user selection), not RESTORE or EXTERNAL (programmatic).

        Args:
            e: FileSelection event (phase="state") containing the selected file/path and origin.
        """
        if e.origin in {SelectionOrigin.RESTORE, SelectionOrigin.EXTERNAL}:
            return

        path = e.path
        if path is None and e.file is not None and hasattr(e.file, "path"):
            path = str(e.file.path)

        if path:
            self._app_config.set_last_selected_file_path(path)
            self._app_config.save()
            logger.info(f"stored selection {path!r} -> app_config.last_selected_file_path")
