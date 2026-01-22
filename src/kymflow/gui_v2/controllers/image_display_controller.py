"""Controller for handling image display change events from the UI.

This module provides a controller that translates user display parameter intents
(ImageDisplayChange phase="intent") into AppState updates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import ImageDisplayChange

if TYPE_CHECKING:
    pass


class ImageDisplayController:
    """Apply image display change events to AppState.

    This controller handles display parameter intent events from the UI (typically
    from the contrast widget) and updates AppState accordingly.

    Display Flow:
        1. User changes slider/colorscale → ContrastView emits ImageDisplayChange(phase="intent")
        2. This controller receives event → calls AppState.set_image_display(params)
        3. AppState callback → AppStateBridge emits ImageDisplayChange(phase="state")
        4. ContrastBindings and ImageLineViewerBindings receive event and update views

    Attributes:
        _app_state: AppState instance to update.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize image display controller.

        Subscribes to ImageDisplayChange (phase="intent") events from the bus.

        Args:
            app_state: AppState instance to update.
            bus: EventBus instance to subscribe to.
        """
        self._app_state: AppState = app_state
        bus.subscribe_intent(ImageDisplayChange, self._on_image_display_change)

    def _on_image_display_change(self, e: ImageDisplayChange) -> None:
        """Handle ImageDisplayChange intent event.

        Updates AppState with the new display parameters.

        Args:
            e: ImageDisplayChange event (phase="intent") containing the display parameters.
        """
        self._app_state.set_image_display(e.params)
