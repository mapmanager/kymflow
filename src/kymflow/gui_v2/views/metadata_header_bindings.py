"""Bindings between MetadataHeaderView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import FileSelection, MetadataUpdate
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.gui_v2.views.metadata_header_view import MetadataHeaderView

if TYPE_CHECKING:
    pass


class MetadataHeaderBindings:
    """Bind MetadataHeaderView to event bus for state → view updates.

    This class subscribes to state change events from AppState (via the bridge)
    and updates the header metadata view accordingly. The view is reactive
    and doesn't initiate actions (except for user interactions, which emit intent events).

    Event Flow:
        1. FileSelection(phase="state") → view.set_selected_file()
        2. MetadataUpdate(phase="state") → view.set_selected_file() (refresh if matches current)

    Attributes:
        _bus: EventBus instance for subscribing to events.
        _view: MetadataHeaderView instance to update.
        _subscribed: Whether subscriptions are active (for cleanup).
    """

    def __init__(self, bus: EventBus, view: MetadataHeaderView) -> None:
        """Initialize header metadata bindings.

        Subscribes to state change events. Since EventBus now uses per-client
        isolation and deduplicates handlers, duplicate subscriptions are automatically
        prevented.

        Args:
            bus: EventBus instance for this client.
            view: MetadataHeaderView instance to update.
        """
        self._bus: EventBus = bus
        self._view: MetadataHeaderView = view
        self._subscribed: bool = False

        # Subscribe to state change events
        bus.subscribe_state(FileSelection, self._on_file_selection_changed)
        bus.subscribe_state(MetadataUpdate, self._on_metadata_update)
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

        self._bus.unsubscribe_state(FileSelection, self._on_file_selection_changed)
        self._bus.unsubscribe_state(MetadataUpdate, self._on_metadata_update)
        self._bus.unsubscribe_state(TaskStateChanged, self._on_task_state_changed)
        self._subscribed = False

    def _on_file_selection_changed(self, e: FileSelection) -> None:
        """Handle file selection change event.

        Updates view for new file selection. Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: FileSelection event (phase="state") containing the selected file.
        """
        safe_call(self._view.set_selected_file, e.file)

    def _on_metadata_update(self, e: MetadataUpdate) -> None:
        """Handle metadata update event.

        Refreshes view if the updated file matches the currently selected file
        and the metadata type is "header". Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: MetadataUpdate event (phase="state") containing the file whose metadata was updated.
        """
        # Only refresh if this is a header metadata update
        if e.metadata_type == "header":
            safe_call(self._view.set_selected_file, e.file)

    def _on_task_state_changed(self, e: TaskStateChanged) -> None:
        """Handle task state changes by disabling/enabling inputs."""
        if e.task_type == "home":
            safe_call(self._view.set_task_state, e)
