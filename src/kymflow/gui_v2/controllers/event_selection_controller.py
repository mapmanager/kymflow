"""Controller for handling velocity event selection events from the UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import EventSelection, SelectionOrigin
from kymflow.gui_v2.state import AppState

if TYPE_CHECKING:
    pass


class EventSelectionController:
    """Apply EventSelection intent events to AppState."""

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize event selection controller.

        Subscribes to EventSelection (phase="intent") events from the bus.
        """
        self._app_state: AppState = app_state
        bus.subscribe_intent(EventSelection, self._on_event_selected)

    def _on_event_selected(self, e: EventSelection) -> None:
        """Handle EventSelection intent event."""
        if e.origin != SelectionOrigin.EVENT_TABLE:
            return

        self._app_state.select_event(
            event_id=e.event_id,
            roi_id=e.roi_id,
            path=e.path,
            event=e.event,
            options=e.options,
            origin=e.origin,
        )
