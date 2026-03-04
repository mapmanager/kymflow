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


def test_dataclass_editor_card_contains_no_detection_specific_motion_logic() -> None:
    import inspect
    import gui.widgets as widgets

    src = inspect.getsource(widgets.dataclass_editor_card)
    assert "enable_motion_constraints" not in src
    assert "motion_fields" not in src
