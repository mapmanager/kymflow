from __future__ import annotations

import numpy as np
import pytest

from kymflow.core.analysis.diameter_analysis import DiameterAnalyzer, DiameterDetectionParams, DiameterMethod
from kymflow.core.analysis.diameter_analysis.diameter_plots import plot_kymograph_with_edges_mpl, plot_kymograph_with_edges_plotly_dict
from kymflow.core.analysis.diameter_analysis import generate_synthetic_kymograph


def test_gradient_edges_runs_and_is_mostly_ordered() -> None:
    payload = generate_synthetic_kymograph(n_time=150, n_space=120, seed=10)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(
        stride=2,
        window_rows_odd=5,
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        gradient_sigma=1.5,
        max_edge_shift_um_on=False,
        max_diameter_change_um_on=False,
        max_center_shift_um_on=False,
    )
    results = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="serial",
    )

    valid = [r for r in results if np.isfinite(r.left_edge_px) and np.isfinite(r.right_edge_px)]
    assert len(valid) / len(results) > 0.8
    assert all(r.left_edge_px < r.right_edge_px for r in valid)


def test_gradient_edges_serial_threads_identical() -> None:
    payload = generate_synthetic_kymograph(n_time=180, n_space=128, seed=4)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(
        stride=3,
        window_rows_odd=7,
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        gradient_sigma=1.2,
    )

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
        assert np.isclose(a.left_edge_px, b.left_edge_px, equal_nan=True)
        assert np.isclose(a.right_edge_px, b.right_edge_px, equal_nan=True)
        assert np.isclose(a.diameter_px, b.diameter_px, equal_nan=True)
        assert np.isclose(a.edge_strength_left, b.edge_strength_left, equal_nan=True)
        assert np.isclose(a.edge_strength_right, b.edge_strength_right, equal_nan=True)
        assert np.isclose(a.qc_score, b.qc_score)
        assert a.qc_flags == b.qc_flags


@pytest.mark.parametrize("mae_tol", [3.0, 4.5])
def test_gradient_edges_accuracy_vs_truth(mae_tol: float) -> None:
    payload = generate_synthetic_kymograph(n_time=180, n_space=128, seed=22, noise_sigma=0.0)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(
        stride=1,
        window_rows_odd=1,
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        gradient_sigma=1.0,
    )

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


def test_plot_orientation_uses_transposed_shape() -> None:
    payload = generate_synthetic_kymograph(n_time=48, n_space=96, seed=3)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(diameter_method=DiameterMethod.GRADIENT_EDGES, stride=2)
    results = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="serial",
    )

    fig = plot_kymograph_with_edges_mpl(
        payload["kymograph"],
        results,
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
    )
    arr = fig.axes[0].images[0].get_array()
    assert arr.shape == (96, 48)

    plotly_dict = plot_kymograph_with_edges_plotly_dict(
        payload["kymograph"],
        results,
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
    )
    z = np.asarray(plotly_dict["data"][0]["z"])
    assert z.shape == (96, 48)
