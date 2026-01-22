"""Controller for handling ROI selection events from the UI.

This module provides a controller that translates user ROI selection intents
(ROISelection phase="intent" events) into AppState updates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import ROISelection

if TYPE_CHECKING:
    pass


class ROISelectionController:
    """Apply ROI selection events to AppState.

    This controller handles ROI selection intent events from the UI (typically
    from the image/line viewer ROI dropdown) and updates AppState accordingly.

    ROI Selection Flow:
        1. User changes ROI dropdown → ImageLineViewerView emits ROISelection(phase="intent", origin=IMAGE_VIEWER)
        2. This controller receives event → calls AppState.select_roi(roi_id)
        3. AppState callback → AppStateBridge emits ROISelection(phase="state", origin=EXTERNAL)
        4. ImageLineViewerBindings receives event, updates viewer

    Note: Two events (intent + state) are expected and correct:
    - Intent event: User action (phase="intent") - what the user wants to do
    - State event: State change (phase="state") - what actually happened
    This allows views to react to state changes without triggering feedback loops.
    The view uses suppression flags to prevent programmatic updates from emitting intent events.

    Attributes:
        _app_state: AppState instance to update.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize ROI selection controller.

        Subscribes to ROISelection (phase="intent") events from the bus.

        Args:
            app_state: AppState instance to update.
            bus: EventBus instance to subscribe to.
        """
        self._app_state: AppState = app_state
        bus.subscribe_intent(ROISelection, self._on_roi_selected)

    def _on_roi_selected(self, e: ROISelection) -> None:
        """Handle ROISelection intent event.

        Updates AppState with the selected ROI ID.

        Args:
            e: ROISelection event (phase="intent") containing the ROI ID and origin.
        """
        # Update AppState with ROI selection
        self._app_state.select_roi(e.roi_id)

