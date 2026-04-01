from __future__ import annotations

from dataclasses import replace

import pytest

from kymflow.core.analysis.diameter_analysis import DiameterDetectionParams
from kymflow.core.analysis.diameter_analysis.gui.widgets import dataclass_editor_card, _coerce_switch_bool


def test_dataclass_editor_card_renders_detection_params() -> None:
    obj = DiameterDetectionParams()
    # Smoke test only: ensure widget creation does not raise.
    card, refresh = dataclass_editor_card(
        obj,
        title="Detection Params",
        on_change=lambda _name, _value: None,
    )
    assert callable(refresh)
    assert hasattr(card, "_editor_widgets")


def test_dataclass_editor_card_contains_no_detection_specific_motion_logic() -> None:
    import inspect
    import kymflow.core.analysis.diameter_analysis.gui.widgets as widgets

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


def test_dataclass_editor_card_refresh_updates_widget_values() -> None:
    obj = DiameterDetectionParams()
    card, refresh = dataclass_editor_card(
        obj,
        title="Detection Params",
        on_change=lambda _name, _value: None,
    )
    widgets = getattr(card, "_editor_widgets")
    assert widgets["gradient_sigma"].value == obj.gradient_sigma
    assert widgets["max_edge_shift_um_on"].value == obj.max_edge_shift_um_on

    updated = replace(obj, gradient_sigma=2.75, max_edge_shift_um_on=False)
    refresh(updated)

    assert widgets["gradient_sigma"].value == 2.75
    assert widgets["max_edge_shift_um_on"].value is False
