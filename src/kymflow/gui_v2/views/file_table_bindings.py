"""Bindings between FileTableView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import FileSelection, SelectionOrigin
from kymflow.gui_v2.events_state import FileListChanged
from kymflow.gui_v2.views.file_table_view import FileTableView

if TYPE_CHECKING:
    pass


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

    def __init__(self, bus: EventBus, table: FileTableView) -> None:
        """Initialize file table bindings.

        Subscribes to FileListChanged and FileSelection (phase="state") events. Since
        EventBus now uses per-client isolation and deduplicates handlers,
        duplicate subscriptions are automatically prevented.

        Args:
            bus: EventBus instance for this client.
            table: FileTableView instance to update.
        """
        self._bus: EventBus = bus
        self._table: FileTableView = table
        self._subscribed: bool = False

        # Subscribe to state change events
        bus.subscribe(FileListChanged, self._on_file_list_changed)
        bus.subscribe_state(FileSelection, self._on_selected_file_changed)
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
        self._subscribed = False

    def _on_file_list_changed(self, e: FileListChanged) -> None:
        """Handle file list change event.

        Updates the table with the new file list from AppState.
        Wrapped in safe_call to handle deleted client errors gracefully.

        Args:
            e: FileListChanged event containing the new file list.
        """
        safe_call(self._table.set_files, e.files)

    def _on_selected_file_changed(self, e: FileSelection) -> None:
        """Handle selected file change event.

        Updates table selection to match AppState, but only if the change
        didn't originate from the table itself (prevents feedback loops).
        Wrapped in safe_call to handle deleted client errors gracefully.

        Args:
            e: FileSelection event (phase="state") containing the new selection and origin.
        """
        # Prevent feedback loop: if selection came from the table, don't re-select
        if e.origin == SelectionOrigin.FILE_TABLE:
            return

        # Update table selection to match AppState (safely handle deleted clients)
        if e.file is None:
            safe_call(self._table.set_selected_paths, [], origin=SelectionOrigin.EXTERNAL)
        else:
            # Use path from event (derived from file) or fall back to file.path
            path = e.path
            if path is None and hasattr(e.file, "path"):
                path = str(e.file.path)
            if path:
                safe_call(self._table.set_selected_paths, [str(path)], origin=SelectionOrigin.EXTERNAL)
            else:
                safe_call(self._table.set_selected_paths, [], origin=SelectionOrigin.EXTERNAL)