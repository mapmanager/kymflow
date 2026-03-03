from __future__ import annotations

import numpy as np

from diameter_analysis import DiameterAnalyzer, DiameterDetectionParams, DiameterMethod
from synthetic_kymograph import generate_synthetic_kymograph


def _make_analyzer() -> DiameterAnalyzer:
    payload = generate_synthetic_kymograph(n_time=180, n_space=128, seed=42, noise_sigma=0.01)
    return DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )


def test_gradient_motion_constraints_produce_nans_and_qc_flags() -> None:
    analyzer = _make_analyzer()
    params = DiameterDetectionParams(
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        window_rows_odd=1,
        stride=1,
        enable_motion_constraints=True,
        max_edge_shift_um=0.001,
        max_diameter_change_um=0.001,
        max_center_shift_um=0.001,
    )
    results = analyzer.analyze(params=params)

    assert any(r.qc_edge_violation or r.qc_diameter_violation or r.qc_center_violation for r in results)
    assert any(np.isnan(r.left_edge_px) or np.isnan(r.right_edge_px) for r in results)
    assert any("motion_" in f for r in results for f in r.qc_flags)


def test_motion_constraints_off_matches_baseline_behavior() -> None:
    analyzer = _make_analyzer()
    base = DiameterDetectionParams(
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        window_rows_odd=1,
        stride=1,
        enable_motion_constraints=False,
    )
    unconstrained = analyzer.analyze(params=base)

    same_cfg_no_violations = DiameterDetectionParams(
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        window_rows_odd=1,
        stride=1,
        enable_motion_constraints=True,
        max_edge_shift_um=1e9,
        max_diameter_change_um=1e9,
        max_center_shift_um=1e9,
    )
    effectively_unconstrained = analyzer.analyze(params=same_cfg_no_violations)

    lhs = np.array([r.diameter_px for r in unconstrained], dtype=float)
    rhs = np.array([r.diameter_px for r in effectively_unconstrained], dtype=float)
    assert np.array_equal(lhs, rhs, equal_nan=True)
    assert all(not r.qc_edge_violation and not r.qc_diameter_violation and not r.qc_center_violation for r in unconstrained)
