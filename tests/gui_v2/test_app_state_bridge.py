"""Tests for AppStateBridgeController behavior."""

from __future__ import annotations

from pathlib import Path

from kymflow.gui_v2.bus import BusConfig, EventBus
from kymflow.gui_v2.controllers.app_state_bridge import AppStateBridgeController
from kymflow.gui_v2.events import ROISelection
from kymflow.gui_v2.state import AppState


class DummyRois:
    def get_roi_ids(self):
        return [1]

    def get(self, _roi_id):
        return object()


class DummyKymImage:
    def __init__(self) -> None:
        self.rois = DummyRois()
        self.path = Path("/tmp/test.tif")

    def getChannelKeys(self):
        return []

    def load_channel(self, _channel):
        return None


def test_bridge_emits_roi_selection_after_file_select() -> None:
    """Selecting a file should emit ROISelection for the default ROI."""
    app_state = AppState()
    bus = EventBus(client_id="test-client", config=BusConfig(trace=False))
    AppStateBridgeController(app_state, bus)

    received: list[ROISelection] = []

    def handler(event: ROISelection) -> None:
        if event.phase == "state":
            received.append(event)

    bus.subscribe_state(ROISelection, handler)

    app_state.select_file(DummyKymImage())

    assert received
    assert received[-1].roi_id == 1
