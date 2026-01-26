"""Controller for handling kym event range state intents from the UI."""

from __future__ import annotations

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import SetKymEventRangeState


class KymEventRangeStateController:
    """Mirror SetKymEventRangeState intent events to state events."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe_intent(SetKymEventRangeState, self._on_set_kym_event_range_state)

    def _on_set_kym_event_range_state(self, e: SetKymEventRangeState) -> None:
        """Emit a state-phase SetKymEventRangeState event for bindings."""
        self._bus.emit(
            SetKymEventRangeState(
                enabled=e.enabled,
                event_id=e.event_id,
                roi_id=e.roi_id,
                path=e.path,
                origin=e.origin,
                phase="state",
            )
        )
