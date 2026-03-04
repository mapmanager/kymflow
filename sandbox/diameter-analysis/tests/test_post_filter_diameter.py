from __future__ import annotations

import numpy as np

from diameter_analysis import (
    DiameterAnalyzer,
    DiameterDetectionParams,
    PostFilterParams,
    PostFilterType,
)
from synthetic_kymograph import generate_synthetic_kymograph


def test_nan_safe_median_filter_removes_single_spike() -> None:
    x = np.array([1.0, 1.1, 9.0, 1.2, 1.0], dtype=float)
    y = DiameterAnalyzer._nan_safe_median_filter(x, kernel_size=3)
    assert np.isclose(y[2], 1.2)
    assert np.isclose(y[1], 1.1)


def test_hampel_filter_replaces_spikes_and_mask() -> None:
    x = np.array([2.0, 2.1, 12.0, 2.2, 2.0, 11.0, 2.1], dtype=float)
    y, mask = DiameterAnalyzer._nan_safe_hampel_filter(
        x,
        kernel_size=3,
        n_sigma=3.0,
        scale="mad",
    )
    assert mask.dtype == bool
    assert mask.sum() >= 2
    assert y[2] < 4.0
    assert y[5] < 4.0


def test_filters_keep_nans_and_no_nan_spread() -> None:
    x = np.array([1.0, np.nan, 10.0, 1.0, np.nan, 1.1], dtype=float)
    y_med = DiameterAnalyzer._nan_safe_median_filter(x, kernel_size=3)
    y_hmp, _ = DiameterAnalyzer._nan_safe_hampel_filter(
        x,
        kernel_size=3,
        n_sigma=3.0,
        scale="mad",
    )
    assert np.isnan(y_med[1]) and np.isnan(y_med[4])
    assert np.isnan(y_hmp[1]) and np.isnan(y_hmp[4])
    assert np.isfinite(y_med[0]) and np.isfinite(y_med[5])


def test_filter_determinism() -> None:
    x = np.array([1.0, 1.2, 8.0, 1.1, 1.0, np.nan, 1.1], dtype=float)
    a_med = DiameterAnalyzer._nan_safe_median_filter(x, kernel_size=3)
    b_med = DiameterAnalyzer._nan_safe_median_filter(x, kernel_size=3)
    assert np.array_equal(a_med, b_med, equal_nan=True)

    a_hmp, a_mask = DiameterAnalyzer._nan_safe_hampel_filter(
        x,
        kernel_size=3,
        n_sigma=3.0,
        scale="mad",
    )
    b_hmp, b_mask = DiameterAnalyzer._nan_safe_hampel_filter(
        x,
        kernel_size=3,
        n_sigma=3.0,
        scale="mad",
    )
    assert np.array_equal(a_hmp, b_hmp, equal_nan=True)
    assert np.array_equal(a_mask, b_mask)


def test_analysis_with_post_filter_preserves_raw_and_filtered() -> None:
    payload = generate_synthetic_kymograph(n_time=120, n_space=96, seed=12)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )

    det = DiameterDetectionParams(stride=1, window_rows_odd=1)
    pf = PostFilterParams(enabled=True, filter_type=PostFilterType.HAMPEL, kernel_size=5)
    results = analyzer.analyze(
        det,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="serial",
        post_filter_params=pf,
    )

    assert len(results) > 0
    raw = np.array([r.diameter_px for r in results], dtype=float)
    filt = np.array([r.diameter_px_filt for r in results], dtype=float)
    assert np.isfinite(raw).sum() > 0
    assert np.isfinite(filt).sum() > 0
    assert all(hasattr(r, "diameter_was_filtered") for r in results)


def test_save_load_roundtrip_contains_post_filter_params(tmp_path) -> None:
    payload = generate_synthetic_kymograph(n_time=80, n_space=80, seed=2)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    det = DiameterDetectionParams(stride=2, window_rows_odd=3)
    pf = PostFilterParams(enabled=True, filter_type=PostFilterType.MEDIAN, kernel_size=3)
    results = analyzer.analyze(
        det,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="serial",
        post_filter_params=pf,
    )

    analyzer.save_analysis(
        tmp_path,
        params_by_roi={1: det},
        results_by_roi={1: results},
        um_per_pixel=payload["um_per_pixel"],
        post_filter_params_by_roi={1: pf},
    )
    loaded = analyzer.load_analysis(tmp_path)
    assert "post_filter_params_by_roi" in loaded
    assert loaded["post_filter_params_by_roi"][1] == pf
