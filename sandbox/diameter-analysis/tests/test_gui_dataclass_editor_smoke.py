from __future__ import annotations

from diameter_analysis import DiameterDetectionParams
from gui.widgets import dataclass_editor_card


def test_dataclass_editor_card_renders_detection_params() -> None:
    obj = DiameterDetectionParams()
    # Smoke test only: ensure widget creation does not raise.
    dataclass_editor_card(
        obj,
        title="Detection Params",
        on_change=lambda _name, _value: None,
    )
