from __future__ import annotations

import pytest

from diameter_analysis import DiameterDetectionParams
from gui.widgets import dataclass_editor_card, _coerce_switch_bool


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


def test_switch_bool_coercion_is_strict() -> None:
    assert _coerce_switch_bool(True) is True
    assert _coerce_switch_bool(False) is False
    assert _coerce_switch_bool({"value": "false"}) is False
    assert _coerce_switch_bool({"value": "true"}) is True
    with pytest.raises(ValueError):
        _coerce_switch_bool("maybe")
