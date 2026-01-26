"""Controller for handling delete kym event intent events from the UI."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import DeleteKymEvent, SelectionOrigin
from kymflow.gui_v2.state import AppState

logger = get_logger(__name__)


class DeleteKymEventController:
    """Apply delete kym event intents to the underlying KymAnalysis."""

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        self._app_state = app_state
        self._bus = bus
        bus.subscribe_intent(DeleteKymEvent, self._on_delete_event)

    def _on_delete_event(self, e: DeleteKymEvent) -> None:
        """Handle DeleteKymEvent intent event."""
        if e.origin != SelectionOrigin.EVENT_TABLE:
            return
        logger.debug("DeleteKymEvent intent event_id=%s", e.event_id)

        kym_file = None
        if e.path is not None:
            for f in self._app_state.files:
                if str(f.path) == e.path:
                    kym_file = f
                    break
        if kym_file is None:
            kym_file = self._app_state.selected_file
        if kym_file is None:
            logger.warning("DeleteKymEvent: no file available (path=%s)", e.path)
            return

        deleted = kym_file.get_kym_analysis().delete_velocity_event(e.event_id)
        if not deleted:
            logger.warning(
                "DeleteKymEvent: event not found (event_id=%s, path=%s)",
                e.event_id,
                e.path,
            )
            return

        logger.debug("DeleteKymEvent: deleted event_id=%s", e.event_id)

        self._bus.emit(
            DeleteKymEvent(
                event_id=e.event_id,
                roi_id=e.roi_id,
                path=e.path,
                origin=e.origin,
                phase="state",
            )
        )
