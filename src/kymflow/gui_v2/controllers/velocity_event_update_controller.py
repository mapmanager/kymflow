"""Controller for handling velocity event update events from the UI."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import SelectionOrigin, VelocityEventUpdate
from kymflow.gui_v2.state import AppState

logger = get_logger(__name__)


class VelocityEventUpdateController:
    """Apply velocity event update intents to the underlying KymAnalysis."""

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        self._app_state = app_state
        self._bus = bus
        bus.subscribe_intent(VelocityEventUpdate, self._on_event_update)

    def _on_event_update(self, e: VelocityEventUpdate) -> None:
        """Handle VelocityEventUpdate intent event."""
        if e.origin != SelectionOrigin.EVENT_TABLE:
            return

        kym_file = None
        if e.path is not None:
            for f in self._app_state.files:
                if str(f.path) == e.path:
                    kym_file = f
                    break
        if kym_file is None:
            kym_file = self._app_state.selected_file
        if kym_file is None:
            return

        updated = kym_file.get_kym_analysis().update_velocity_event_field(
            event_id=e.event_id,
            field=e.field,
            value=e.value,
        )
        if not updated:
            logger.warning(
                "VelocityEventUpdate: event not found (event_id=%s, path=%s)",
                e.event_id,
                e.path,
            )
            return

        self._bus.emit(
            VelocityEventUpdate(
                event_id=e.event_id,
                path=e.path,
                field=e.field,
                value=e.value,
                origin=e.origin,
                phase="state",
            )
        )
