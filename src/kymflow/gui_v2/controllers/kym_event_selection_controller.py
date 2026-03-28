"""Controller for handling velocity event selection events from the UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import KymEventSelection, SelectionOrigin
from kymflow.gui_v2.state import AppState
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

class KymEventSelectionController:
    """Apply KymEventSelection intent events to AppState."""

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize kym event selection controller.

        Subscribes to KymEventSelection (phase="intent") events from the bus.
        """
        self._app_state: AppState = app_state
        bus.subscribe_intent(KymEventSelection, self._on_event_selected)

    def _on_event_selected(self, e: KymEventSelection) -> None:
        """Handle KymEventSelection intent event."""
                
        if e.origin != SelectionOrigin.EVENT_TABLE:
            return

        logger.error('    calling self._app_state.select_velocity_event() -->> -->>')


        self._app_state.select_velocity_event(
            event_id=e.event_id,
            roi_id=e.roi_id,
            path=e.path,
            event=e.event,
            options=e.options,
            origin=e.origin,
        )
