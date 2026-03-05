from __future__ import annotations

from pathlib import Path

import pytest

import diameter_analysis as da
from diameter_analysis import DiameterDetectionParams, DiameterResult
from gui.controllers import AppController
from gui.models import AppState


def _one_result() -> DiameterResult:
    return DiameterResult(
        roi_id=1,
        channel_id=1,
        center_row=0,
        time_s=0.0,
        left_edge_px=10.0,
        right_edge_px=20.0,
        diameter_px=10.0,
        peak=1.0,
        baseline=0.0,
        edge_strength_left=0.1,
        edge_strength_right=0.1,
        diameter_px_filt=10.0,
        diameter_was_filtered=False,
        qc_score=1.0,
        qc_flags=[],
        qc_edge_violation=False,
        qc_diameter_violation=False,
        qc_center_violation=False,
    )


def test_save_analysis_fails_fast_without_results() -> None:
    controller = AppController(AppState())
    controller.state.loaded_path = "/tmp/example.tif"
    with pytest.raises(RuntimeError, match="No analysis results to save"):
        controller.save_analysis()


def test_save_analysis_calls_backend_with_loaded_path(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = AppController(AppState())
    controller.state.loaded_path = "/tmp/example.tif"
    controller.state.results = [_one_result()]
    controller.state.detection_params = DiameterDetectionParams(stride=2, gradient_sigma=3.0)

    called: dict[str, object] = {}

    def _fake_save(
        kym_path: str | Path,
        bundle: da.DiameterAnalysisBundle,
        *,
        detection_params_by_run: dict[tuple[int, int], DiameterDetectionParams],
        out_dir: Path | None = None,
    ):
        called["kym_path"] = str(kym_path)
        called["keys"] = sorted(bundle.runs.keys())
        called["len_run"] = len(bundle.runs[(1, 1)])
        called["params_keys"] = sorted(detection_params_by_run.keys())
        called["stride"] = detection_params_by_run[(1, 1)].stride
        called["out_dir"] = out_dir
        return Path("/tmp/example.diameter.json"), Path("/tmp/example.diameter.csv")

    monkeypatch.setattr(da, "save_diameter_analysis", _fake_save)
    out = controller.save_analysis()

    assert called["kym_path"] == "/tmp/example.tif"
    assert called["keys"] == [(1, 1)]
    assert called["len_run"] == 1
    assert called["params_keys"] == [(1, 1)]
    assert called["stride"] == 2
    assert called["out_dir"] is None
    assert out[0].name == "example.diameter.json"
    assert out[1].name == "example.diameter.csv"


def test_try_load_saved_analysis_populates_results_and_detection_params(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = AppController(AppState())
    controller.state.loaded_path = str(tmp_path / "example.tif")
    (tmp_path / "example.diameter.json").write_text("{}", encoding="utf-8")
    (tmp_path / "example.diameter.csv").write_text("time_s\n", encoding="utf-8")

    params = DiameterDetectionParams(stride=5, gradient_sigma=1.1)
    bundle = da.DiameterAnalysisBundle(runs={(1, 1): [_one_result()]})

    monkeypatch.setattr(da, "load_diameter_analysis", lambda _path: (bundle, {(1, 1): params}))

    loaded = controller.try_load_saved_analysis()
    assert loaded is True
    assert isinstance(controller.state.results, list)
    assert len(controller.state.results) == 1
    assert controller.state.detection_params == params
