"""Bindings between TaskProgressView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.gui_v2.views.task_progress_view import TaskProgressView

if TYPE_CHECKING:
    pass


class TaskProgressBindings:
    """Bind TaskProgressView to event bus for state → view updates.

    This class subscribes to state change events from TaskState (via the bridge)
    and updates the task progress view accordingly. The view is reactive and
    doesn't initiate actions.

    Event Flow:
        1. TaskStateChanged → view.set_task_state() (update progress bar and status)

    Attributes:
        _bus: EventBus instance for subscribing to events.
        _view: TaskProgressView instance to update.
        _subscribed: Whether subscriptions are active (for cleanup).
    """

    def __init__(self, bus: EventBus, view: TaskProgressView) -> None:
        """Initialize task progress bindings.

        Subscribes to state change events. Since EventBus now uses per-client
        isolation and deduplicates handlers, duplicate subscriptions are automatically
        prevented.

        Args:
            bus: EventBus instance for this client.
            view: TaskProgressView instance to update.
        """
        self._bus: EventBus = bus
        self._view: TaskProgressView = view
        self._subscribed: bool = False

        # Subscribe to state change events
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

        self._bus.unsubscribe_state(TaskStateChanged, self._on_task_state_changed)
        self._subscribed = False

    def _on_task_state_changed(self, e: TaskStateChanged) -> None:
        """Handle task state change event.

        Updates view progress bar and status message based on task state.
        Only processes events for "home" task type. Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: TaskStateChanged event containing task state information.
        """
        # Only process "home" task type events for this progress view
        if e.task_type == "home":
            safe_call(self._view.set_task_state, e)
