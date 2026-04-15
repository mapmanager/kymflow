from __future__ import annotations

from dataclasses import fields

from kymflow.core.analysis.diameter_analysis import DiameterDetectionParams
from kymflow.core.analysis.diameter_analysis.gui.widgets import _field_help_text


def test_detection_params_metadata_has_description_and_units() -> None:
    for f in fields(DiameterDetectionParams):
        description = str(f.metadata.get("description", "")).strip()
        units = str(f.metadata.get("units", "")).strip()
        assert description, f"missing description metadata for {f.name}"
        assert units, f"missing units metadata for {f.name}"


def test_detection_params_metadata_methods_is_list_when_present() -> None:
    for f in fields(DiameterDetectionParams):
        methods = f.metadata.get("methods", None)
        if methods is None:
            continue
        assert isinstance(methods, list), f"methods metadata must be list for {f.name}"
        assert methods, f"methods metadata must not be empty for {f.name}"


def test_widget_help_text_uses_detection_param_metadata() -> None:
    field_by_name = {f.name: f for f in fields(DiameterDetectionParams)}
    help_text = _field_help_text(field_by_name["gradient_sigma"].metadata)
    assert "Gaussian smoothing sigma" in help_text
    assert "units: px" in help_text
    assert "methods: gradient_edges" in help_text


def test_detection_params_removed_roi_and_enable_motion_constraints() -> None:
    obj = DiameterDetectionParams()
    assert not hasattr(obj, "roi")
    assert not hasattr(obj, "enable_motion_constraints")


def test_detection_params_new_motion_toggles_default_true() -> None:
    obj = DiameterDetectionParams()
    assert obj.max_edge_shift_um_on is True
    assert obj.max_diameter_change_um_on is True
    assert obj.max_center_shift_um_on is True
