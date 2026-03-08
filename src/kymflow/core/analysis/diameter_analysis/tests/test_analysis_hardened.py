from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from diameter_analysis import (
    DiameterAnalysisBundle,
    DiameterAnalyzer,
    DiameterDetectionParams,
    load_diameter_analysis,
    save_diameter_analysis,
)
from synthetic_kymograph import generate_synthetic_kymograph


def test_stride_semantics_center_row_and_time() -> None:
    payload = generate_synthetic_kymograph(n_time=60, n_space=80, seed=5)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(stride=4, window_rows_odd=5)
    results = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="serial",
    )

    expected_centers = list(range(0, 60, 4))
    assert [r.center_row for r in results] == expected_centers
    assert np.allclose(
        np.array([r.time_s for r in results]),
        np.array(expected_centers, dtype=float) * payload["seconds_per_line"],
    )


def test_serial_and_threads_backends_match() -> None:
    payload = generate_synthetic_kymograph(n_time=180, n_space=120, seed=4)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(stride=3, window_rows_odd=7)

    serial = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="serial",
    )
    threaded = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="threads",
    )

    assert len(serial) == len(threaded)
    for a, b in zip(serial, threaded):
        assert a.center_row == b.center_row
        assert np.isclose(a.time_s, b.time_s)
        assert np.isclose(a.left_edge_px, b.left_edge_px, equal_nan=True)
        assert np.isclose(a.right_edge_px, b.right_edge_px, equal_nan=True)
        assert np.isclose(a.diameter_px, b.diameter_px, equal_nan=True)
        assert np.isclose(a.peak, b.peak)
        assert np.isclose(a.baseline, b.baseline)
        assert np.isclose(a.qc_score, b.qc_score)
        assert a.qc_flags == b.qc_flags


def test_save_load_roundtrip_schema_and_row_count(tmp_path: Path) -> None:
    payload = generate_synthetic_kymograph(n_time=72, n_space=96, seed=2)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )

    params = DiameterDetectionParams(stride=3, window_rows_odd=5)
    results = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="serial",
    )

    kym_path = tmp_path / "roundtrip.tif"
    run_key = (1, 1)
    json_path, csv_path = save_diameter_analysis(
        kym_path,
        DiameterAnalysisBundle(runs={run_key: results}),
        roi_bounds_by_run={run_key: (0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1])},
        detection_params_by_run={run_key: params},
    )
    loaded_bundle, loaded_params, loaded_bounds, warnings = load_diameter_analysis(kym_path)
    assert json_path.name == "roundtrip.diameter.json"
    assert csv_path.name == "roundtrip.diameter.csv"
    assert warnings == []
    assert set(loaded_bundle.runs) == {run_key}
    assert loaded_params[run_key] == params
    assert loaded_bounds[run_key] == (0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1])
    assert len(loaded_bundle.runs[run_key]) == len(results)

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(results)


@pytest.mark.parametrize("mae_tol", [2.5, 3.5])
def test_synthetic_truth_and_threshold_width_accuracy(mae_tol: float) -> None:
    payload = generate_synthetic_kymograph(n_time=160, n_space=128, seed=7, noise_sigma=0.0)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(stride=1, window_rows_odd=1)
    results = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="serial",
    )

    truth = np.asarray(payload["truth"]["truth_diameter_px"], dtype=float)
    centers = np.array([r.center_row for r in results], dtype=int)
    estimate = np.array([r.diameter_px for r in results], dtype=float)

    aligned_truth = truth[centers]
    valid = np.isfinite(estimate) & np.isfinite(aligned_truth)
    assert valid.mean() > 0.8
    mae = np.mean(np.abs(estimate[valid] - aligned_truth[valid]))
    assert mae <= mae_tol


def test_missing_edges_do_not_crash_and_qc_flagged() -> None:
    payload = generate_synthetic_kymograph(n_time=40, n_space=60, seed=11)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(
        stride=2,
        window_rows_odd=3,
        threshold_mode="absolute",
        threshold_value=1e9,
    )
    results = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="serial",
    )

    assert len(results) > 0
    assert any(
        ("missing_left_edge" in r.qc_flags) or ("missing_right_edge" in r.qc_flags) for r in results
    )
    assert any(not np.isfinite(r.diameter_px) for r in results)
