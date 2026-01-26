"""Controller for handling add kym event intent events from the UI."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import AddKymEvent, SelectionOrigin
from kymflow.gui_v2.state import AppState

logger = get_logger(__name__)


class AddKymEventController:
    """Apply add kym event intents to the underlying KymAnalysis."""

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        self._app_state = app_state
        self._bus = bus
        bus.subscribe_intent(AddKymEvent, self._on_add_event)

    def _on_add_event(self, e: AddKymEvent) -> None:
        """Handle AddKymEvent intent event."""
        if e.origin != SelectionOrigin.EVENT_TABLE:
            return
        logger.debug("AddKymEvent intent roi_id=%s t_start=%s t_end=%s", e.roi_id, e.t_start, e.t_end)

        kym_file = None
        if e.path is not None:
            for f in self._app_state.files:
                if str(f.path) == e.path:
                    kym_file = f
                    break
        if kym_file is None:
            kym_file = self._app_state.selected_file
        if kym_file is None:
            logger.warning("AddKymEvent: no file available (path=%s)", e.path)
            return

        try:
            event_id = kym_file.get_kym_analysis().add_velocity_event(
                roi_id=e.roi_id,
                t_start=e.t_start,
                t_end=e.t_end,
            )
            logger.debug("AddKymEvent: created event_id=%s", event_id)

            self._bus.emit(
                AddKymEvent(
                    event_id=event_id,
                    roi_id=e.roi_id,
                    path=e.path,
                    t_start=e.t_start,
                    t_end=e.t_end,
                    origin=e.origin,
                    phase="state",
                )
            )
        except ValueError as exc:
            logger.warning("AddKymEvent: failed to create event: %s", exc)
