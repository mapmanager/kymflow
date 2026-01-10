"""Bindings between SaveButtonsView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import FileSelection
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.gui_v2.views.save_buttons_view import SaveButtonsView

if TYPE_CHECKING:
    pass


class SaveButtonsBindings:
    """Bind SaveButtonsView to event bus for state → view updates.

    This class subscribes to state change events from AppState and TaskState
    (via the bridge) and updates the save buttons view accordingly. The view
    is reactive and doesn't initiate actions (except for user interactions,
    which emit intent events).

    Event Flow:
        1. FileSelection(phase="state") → view.set_selected_file()
        2. TaskStateChanged → view.set_task_state() (update button states)

    Attributes:
        _bus: EventBus instance for subscribing to events.
        _view: SaveButtonsView instance to update.
        _subscribed: Whether subscriptions are active (for cleanup).
    """

    def __init__(self, bus: EventBus, view: SaveButtonsView) -> None:
        """Initialize save buttons bindings.

        Subscribes to state change events. Since EventBus now uses per-client
        isolation and deduplicates handlers, duplicate subscriptions are automatically
        prevented.

        Args:
            bus: EventBus instance for this client.
            view: SaveButtonsView instance to update.
        """
        self._bus: EventBus = bus
        self._view: SaveButtonsView = view
        self._subscribed: bool = False

        # Subscribe to state change events
        bus.subscribe_state(FileSelection, self._on_file_selection_changed)
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

    def _on_task_state_changed(self, e: TaskStateChanged) -> None:
        """Handle task state change event.

        Updates view button states based on task running state.
        Only processes events for "home" task type. Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: TaskStateChanged event containing task state information.
        """
        # Only process "home" task type events for this view
        if e.task_type == "home":
            safe_call(self._view.set_task_state, e)
