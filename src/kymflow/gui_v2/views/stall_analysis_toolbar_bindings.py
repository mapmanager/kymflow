"""Bindings between StallAnalysisToolbarView and event bus (state → view updates).

DEPRECATED: Stall analysis is deprecated. This module is kept for reference
but should not be used. The implementation is commented out to prevent usage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import FileSelection, ROISelection
from kymflow.gui_v2.views.stall_analysis_toolbar_view import StallAnalysisToolbarView

if TYPE_CHECKING:
    pass


class StallAnalysisToolbarBindings:
    """Bind StallAnalysisToolbarView to event bus for state → view updates.

    This class subscribes to state change events from AppState (via the bridge)
    and updates the stall analysis toolbar view accordingly. The view is reactive
    and doesn't initiate actions (except for button clicks, which run analysis).

    Event Flow:
        1. FileSelection(phase="state") → view.set_selected_file()
        2. ROISelection(phase="state") → view.set_selected_roi()

    Attributes:
        _bus: EventBus instance for subscribing to events.
        _view: StallAnalysisToolbarView instance to update.
        _subscribed: Whether subscriptions are active (for cleanup).
    """

    def __init__(self, bus: EventBus, view: StallAnalysisToolbarView) -> None:
        """Initialize stall analysis toolbar bindings.

        Subscribes to state change events. Since EventBus now uses per-client
        isolation and deduplicates handlers, duplicate subscriptions are automatically
        prevented.

        Args:
            bus: EventBus instance for this client.
            view: StallAnalysisToolbarView instance to update.
        """
        self._bus: EventBus = bus
        self._view: StallAnalysisToolbarView = view
        self._subscribed: bool = False

        # Subscribe to state change events
        bus.subscribe_state(FileSelection, self._on_file_selection_changed)
        bus.subscribe_state(ROISelection, self._on_roi_selection_changed)
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
        self._bus.unsubscribe_state(ROISelection, self._on_roi_selection_changed)
        self._subscribed = False

    def _on_file_selection_changed(self, e: FileSelection) -> None:
        """Handle file selection change event.

        Updates view for new file selection. Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: FileSelection event (phase="state") containing the selected file.
        """
        safe_call(self._view.set_selected_file, e.file)

    def _on_roi_selection_changed(self, e: ROISelection) -> None:
        """Handle ROI selection change event.

        Updates view for new ROI selection. Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: ROISelection event (phase="state") containing the selected ROI ID.
        """
        safe_call(self._view.set_selected_roi, e.roi_id)
