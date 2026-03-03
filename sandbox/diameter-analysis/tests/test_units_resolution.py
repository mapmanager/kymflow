from __future__ import annotations

import numpy as np

from gui.controllers import AppController
from gui.models import AppState


class _DummyKymImage:
    def __init__(self, path: str, seconds_per_line: float, um_per_pixel: float) -> None:
        self.path = path
        self.seconds_per_line = seconds_per_line
        self.um_per_pixel = um_per_pixel


class _DummySyntheticParams:
    def __init__(self, seconds_per_line: float, um_per_pixel: float) -> None:
        self.seconds_per_line = seconds_per_line
        self.um_per_pixel = um_per_pixel


def test_detect_uses_selected_kym_image_units(monkeypatch) -> None:
    captured: dict[str, float] = {}

    class _FakeAnalyzer:
        def __init__(self, _img, *, seconds_per_line: float, um_per_pixel: float, polarity: str) -> None:
            captured["seconds_per_line"] = seconds_per_line
            captured["um_per_pixel"] = um_per_pixel
            captured["polarity"] = polarity

        def analyze(self, params):
            return []

    monkeypatch.setattr("diameter_analysis.DiameterAnalyzer", _FakeAnalyzer)

    state = AppState()
    controller = AppController(state)
    selected = _DummyKymImage(path="/tmp/a.tif", seconds_per_line=0.003, um_per_pixel=0.21)
    state.detection_params = object()
    controller.set_img(np.ones((4, 6), dtype=float), source="tiff", selected_kym_image=selected)

    controller.detect()

    assert captured["seconds_per_line"] == 0.003
    assert captured["um_per_pixel"] == 0.21


def test_detect_uses_synthetic_params_units(monkeypatch) -> None:
    captured: dict[str, float] = {}

    class _FakeAnalyzer:
        def __init__(self, _img, *, seconds_per_line: float, um_per_pixel: float, polarity: str) -> None:
            captured["seconds_per_line"] = seconds_per_line
            captured["um_per_pixel"] = um_per_pixel

        def analyze(self, params):
            return []

    monkeypatch.setattr("diameter_analysis.DiameterAnalyzer", _FakeAnalyzer)

    state = AppState()
    state.synthetic_params = _DummySyntheticParams(seconds_per_line=0.006, um_per_pixel=0.19)
    controller = AppController(state)
    state.detection_params = object()
    controller.set_img(np.ones((4, 6), dtype=float), source="synthetic", selected_kym_image=None)

    controller.detect()

    assert captured["seconds_per_line"] == 0.006
    assert captured["um_per_pixel"] == 0.19


def test_kymograph_title_prefers_selected_filename() -> None:
    state = AppState()
    controller = AppController(state)
    state.selected_kym_image = _DummyKymImage(
        path="/tmp/demo/cell_05_C001T001.tif",
        seconds_per_line=0.002,
        um_per_pixel=0.2,
    )
    state.source = "tiff"

    assert controller.kymograph_title() == "cell_05_C001T001.tif"


def test_kymograph_title_for_synthetic() -> None:
    state = AppState()
    controller = AppController(state)
    state.source = "synthetic"
    state.selected_kym_image = None

    assert controller.kymograph_title() == "synthetic"
