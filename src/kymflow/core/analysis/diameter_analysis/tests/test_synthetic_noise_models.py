from __future__ import annotations

import numpy as np

from kymflow.core.analysis.diameter_analysis import DiameterAnalyzer, DiameterDetectionParams
from kymflow.core.analysis.diameter_analysis import SyntheticKymographParams, generate_synthetic_kymograph


def test_backward_compatible_default_float_range_and_params_key() -> None:
    payload = generate_synthetic_kymograph()
    img = payload["kymograph"]

    assert img.dtype == np.float64
    assert np.nanmin(img) >= 0.0
    assert np.nanmax(img) <= 1.0
    assert "synthetic_params" in payload
    assert "meta" in payload


def test_uint16_quantized_11bit_and_nonzero_baseline() -> None:
    params = SyntheticKymographParams(
        n_time=80,
        n_space=100,
        seed=3,
        output_dtype="uint16",
        effective_bits=11,
        clip=True,
        baseline_counts=250.0,
        signal_peak_counts=1200.0,
        bg_gaussian_sigma_frac=0.0,
    )
    payload = generate_synthetic_kymograph(synthetic_params=params)
    img = payload["kymograph"]

    assert img.dtype == np.uint16
    assert int(img.max()) <= 2047
    assert float(np.median(img)) > 0.0


def test_bright_band_saturates_to_max_counts() -> None:
    params = SyntheticKymographParams(
        n_time=60,
        n_space=120,
        seed=4,
        output_dtype="uint16",
        effective_bits=11,
        clip=True,
        baseline_counts=120.0,
        signal_peak_counts=700.0,
        bright_band_enabled=True,
        bright_band_x_center_px=40,
        bright_band_width_px=8,
        bright_band_amplitude_counts=100.0,
        bright_band_saturate=True,
    )
    payload = generate_synthetic_kymograph(synthetic_params=params)
    img = payload["kymograph"]

    max_counts = (2**params.effective_bits) - 1
    x0 = params.bright_band_x_center_px - (params.bright_band_width_px // 2)
    x1 = x0 + params.bright_band_width_px
    x0 = max(0, x0)
    x1 = min(params.n_space, x1)

    band = img[:, x0:x1]
    assert band.size > 0
    assert int(np.max(band)) == max_counts


def test_deterministic_same_seed_and_params() -> None:
    params = SyntheticKymographParams(
        n_time=64,
        n_space=96,
        seed=42,
        output_dtype="uint16",
        baseline_counts=180.0,
        signal_peak_counts=950.0,
        bg_gaussian_sigma_frac=0.02,
        fixed_pattern_col_sigma_counts=4.0,
        speckle_sigma_frac=0.1,
        wall_jitter_px=0.5,
        bright_band_enabled=True,
        bright_band_x_center_px=20,
        bright_band_width_px=5,
        bright_band_amplitude_counts=200.0,
    )

    a = generate_synthetic_kymograph(synthetic_params=params)
    b = generate_synthetic_kymograph(synthetic_params=params)

    assert np.array_equal(a["kymograph"], b["kymograph"])
    assert np.array_equal(a["truth"]["truth_diameter_px"], b["truth"]["truth_diameter_px"])


def test_analysis_runs_on_quantized_data() -> None:
    params = SyntheticKymographParams(
        n_time=90,
        n_space=120,
        seed=5,
        output_dtype="uint16",
        effective_bits=11,
        baseline_counts=220.0,
        signal_peak_counts=1000.0,
        bg_gaussian_sigma_frac=0.01,
        bright_band_enabled=True,
        bright_band_x_center_px=85,
        bright_band_width_px=6,
        bright_band_amplitude_counts=150.0,
    )
    payload = generate_synthetic_kymograph(synthetic_params=params)

    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    results = analyzer.analyze(
        DiameterDetectionParams(stride=2),
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="serial",
    )

    assert len(results) > 0
    diam = np.array([r.diameter_px for r in results], dtype=float)
    assert np.isfinite(diam).sum() > 0
