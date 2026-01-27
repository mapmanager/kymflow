"""Controller for handling ROI edit state intents from the UI."""

from __future__ import annotations

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import SetRoiEditState


class RoiEditStateController:
    """Mirror SetRoiEditState intent events to state events."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe_intent(SetRoiEditState, self._on_set_roi_edit_state)

    def _on_set_roi_edit_state(self, e: SetRoiEditState) -> None:
        """Emit a state-phase SetRoiEditState event for bindings."""
        self._bus.emit(
            SetRoiEditState(
                enabled=e.enabled,
                roi_id=e.roi_id,
                path=e.path,
                origin=e.origin,
                phase="state",
            )
        )
