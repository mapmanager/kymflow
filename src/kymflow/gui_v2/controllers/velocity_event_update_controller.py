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
        logger.debug("VelocityEventUpdate intent event_id=%s", e.event_id)

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

        updates = e.updates
        if updates is None:
            if e.field is None:
                return
            updates = {e.field: e.value}

        # Track new event_id (may change if t_start/t_end are updated)
        new_event_id = e.event_id

        # If both t_start and t_end are being updated, use atomic update to avoid event_id mismatch
        if "t_start" in updates and "t_end" in updates:
            new_event_id = kym_file.get_kym_analysis().update_velocity_event_range(
                event_id=e.event_id,
                t_start=updates["t_start"],
                t_end=updates["t_end"],
            )
            if new_event_id is None:
                logger.warning(
                    "VelocityEventUpdate: event not found (event_id=%s, path=%s)",
                    e.event_id,
                    e.path,
                )
                return
        else:
            # Update fields one at a time
            for field, value in updates.items():
                result = kym_file.get_kym_analysis().update_velocity_event_field(
                    event_id=new_event_id,  # Use updated event_id for subsequent updates
                    field=field,
                    value=value,
                )
                if result is None:
                    logger.warning(
                        "VelocityEventUpdate: event not found (event_id=%s, path=%s)",
                        new_event_id,
                        e.path,
                    )
                    return
                # Update event_id if it changed (e.g., when updating t_start or t_end)
                new_event_id = result

        self._bus.emit(
            VelocityEventUpdate(
                event_id=new_event_id,  # Use new event_id in state event
                path=e.path,
                updates=updates,
                origin=e.origin,
                phase="state",
            )
        )
