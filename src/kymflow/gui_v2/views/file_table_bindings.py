"""Bindings between FileTableView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import FileSelection, MetadataUpdate, SelectionOrigin
from kymflow.gui_v2.events_state import AnalysisCompleted, FileListChanged, TaskStateChanged
from kymflow.gui_v2.views.file_table_view import FileTableView
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    from kymflow.gui_v2.state import AppState

logger = get_logger(__name__)


class FileTableBindings:
    """Bind FileTableView to event bus for state → view updates.

    This class subscribes to state change events from AppState (via the bridge)
    and updates the file table view accordingly. It prevents feedback loops by
    ignoring selection changes that originated from the table itself.

    Selection Flow:
        1. User clicks table row → FileTableView emits FileSelection(phase="intent")
        2. FileSelectionController updates AppState
        3. AppStateBridge emits FileSelection(phase="state")
        4. FileTableBindings receives event, checks origin
        5. If origin != FILE_TABLE, updates table selection (to sync with state)
        6. If origin == FILE_TABLE, ignores (prevents feedback loop)

    Attributes:
        _bus: EventBus instance for subscribing to events.
        _table: FileTableView instance to update.
        _subscribed: Whether subscriptions are active (for cleanup).
    """

    def __init__(self, bus: EventBus, table: FileTableView, app_state: "AppState | None" = None) -> None:
        """Initialize file table bindings.

        Subscribes to FileListChanged and FileSelection (phase="state") events. Since
        EventBus now uses per-client isolation and deduplicates handlers,
        duplicate subscriptions are automatically prevented.

        Args:
            bus: EventBus instance for this client.
            table: FileTableView instance to update.
            app_state: Optional AppState instance to query current selection (for fallback).
        """
        self._bus: EventBus = bus
        self._table: FileTableView = table
        self._app_state: "AppState | None" = app_state
        self._subscribed: bool = False
        self._current_selected_path: str | None = None  # Track currently selected file path

        # Subscribe to state change events
        bus.subscribe(FileListChanged, self._on_file_list_changed)
        bus.subscribe_state(FileSelection, self._on_selected_file_changed)
        bus.subscribe_state(MetadataUpdate, self._on_metadata_update)
        bus.subscribe_state(AnalysisCompleted, self._on_analysis_completed)
        bus.subscribe_state(TaskStateChanged, self._on_task_state_changed)
        self._subscribed = True

    def teardown(self) -> None:
        """Unsubscribe from all events (cleanup).

        Call this when the bindings are no longer needed (e.g., page destroyed).
        EventBus per-client isolation means this is usually not necessary, but
        it's available for explicit cleanup if needed.
        """
        if not self._subscribed:
            return

        self._bus.unsubscribe(FileListChanged, self._on_file_list_changed)
        self._bus.unsubscribe_state(FileSelection, self._on_selected_file_changed)
        self._bus.unsubscribe_state(MetadataUpdate, self._on_metadata_update)
        self._bus.unsubscribe_state(AnalysisCompleted, self._on_analysis_completed)
        self._bus.unsubscribe_state(TaskStateChanged, self._on_task_state_changed)
        self._subscribed = False

    def _on_file_list_changed(self, e: FileListChanged) -> None:
        """Handle file list change event.

        Updates the table with the new file list from AppState.
        Wrapped in safe_call to handle deleted client errors gracefully.

        Args:
            e: FileListChanged event containing the new file list.
        """
        logger.debug("FileTableBindings._on_file_list_changed: files=%s", len(e.files))
        safe_call(self._table.set_files, e.files)

    def _on_selected_file_changed(self, e: FileSelection) -> None:
        """Handle selected file change event.

        Updates table selection to match AppState, but only if the change
        didn't originate from the table itself (prevents feedback loops).
        Wrapped in safe_call to handle deleted client errors gracefully.

        Args:
            e: FileSelection event (phase="state") containing the new selection and origin.
        """
        # Always sync selection from AppState, even if origin was FILE_TABLE.
        # This prevents selection loss when the table is rebuilt during UI updates.

        logger.debug(f'pyinstaller FileSelection e={e}')

        # Track currently selected file path for restoration after metadata updates
        if e.file is None:
            self._current_selected_path = None
            safe_call(self._table.set_selected_paths, [], origin=SelectionOrigin.EXTERNAL)
        else:
            # Use path from event (derived from file) or fall back to file.path
            path = e.path
            if path is None and hasattr(e.file, "path"):
                path = str(e.file.path)
            if path:
                self._current_selected_path = str(path)
                safe_call(self._table.set_selected_paths, [str(path)], origin=SelectionOrigin.EXTERNAL)
            else:
                self._current_selected_path = None
                safe_call(self._table.set_selected_paths, [], origin=SelectionOrigin.EXTERNAL)

    def _on_metadata_update(self, e: MetadataUpdate) -> None:
        """Handle metadata update events by refreshing table rows.
        
        Simply refreshes the table data to show updated metadata (e.g., analysis status),
        while preserving the currently selected file from AppState.
        """
        logger.debug(f'pyinstaller e={e}')
        self._refresh_rows_preserve_selection()

    def _on_analysis_completed(self, e: AnalysisCompleted) -> None:
        """Handle analysis completion by refreshing table rows."""
        logger.debug("analysis_completed file=%s roi_id=%s success=%s", e.file, e.roi_id, e.success)
        if not e.success:
            return
        self._refresh_rows_preserve_selection()

    def _on_task_state_changed(self, e: TaskStateChanged) -> None:
        """Handle task state changes by disabling/enabling table interactions."""
        if e.task_type == "home":
            safe_call(self._table.set_task_state, e)

    def _refresh_rows_preserve_selection(self) -> None:
        """Refresh table rows and restore selection."""

        # Get currently selected file path from AppState (source of truth)
        selected_path = None
        if self._app_state is not None and self._app_state.selected_file is not None:
            if hasattr(self._app_state.selected_file, "path"):
                selected_path = str(self._app_state.selected_file.path)
        
        logger.debug(f'pyinstaller selected_path={selected_path}')
        # Refresh the table rows (this clears selection in the grid)
        safe_call(self._table.refresh_rows)
        
        # Restore selection if we had one (AppState hasn't changed, so restore it)
        if selected_path:
            safe_call(
                self._table.set_selected_paths,
                [selected_path],
                origin=SelectionOrigin.EXTERNAL,
            )