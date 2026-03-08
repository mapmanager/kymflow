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
        max_edge_shift_um_on=True,
        max_diameter_change_um_on=True,
        max_center_shift_um_on=True,
        max_edge_shift_um=0.001,
        max_diameter_change_um=0.001,
        max_center_shift_um=0.001,
    )
    results = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
    )

    assert any(r.qc_edge_violation or r.qc_diameter_violation or r.qc_center_violation for r in results)
    assert any(np.isnan(r.left_edge_px) or np.isnan(r.right_edge_px) for r in results)
    assert any("motion_" in f for r in results for f in r.qc_flags)


def test_motion_constraints_off_matches_baseline_behavior() -> None:
    analyzer = _make_analyzer()
    base = DiameterDetectionParams(
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        window_rows_odd=1,
        stride=1,
        max_edge_shift_um_on=False,
        max_diameter_change_um_on=False,
        max_center_shift_um_on=False,
    )
    unconstrained = analyzer.analyze(
        params=base,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
    )

    same_cfg_no_violations = DiameterDetectionParams(
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        window_rows_odd=1,
        stride=1,
        max_edge_shift_um_on=True,
        max_diameter_change_um_on=True,
        max_center_shift_um_on=True,
        max_edge_shift_um=1e9,
        max_diameter_change_um=1e9,
        max_center_shift_um=1e9,
    )
    effectively_unconstrained = analyzer.analyze(
        params=same_cfg_no_violations,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
    )

    lhs = np.array([r.diameter_px for r in unconstrained], dtype=float)
    rhs = np.array([r.diameter_px for r in effectively_unconstrained], dtype=float)
    assert np.array_equal(lhs, rhs, equal_nan=True)
    assert all(not r.qc_edge_violation and not r.qc_diameter_violation and not r.qc_center_violation for r in unconstrained)


def test_only_enabled_constraint_toggle_applies() -> None:
    analyzer = _make_analyzer()
    base = DiameterDetectionParams(
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        window_rows_odd=1,
        stride=1,
        max_edge_shift_um_on=False,
        max_diameter_change_um_on=False,
        max_center_shift_um_on=False,
    )
    unconstrained = analyzer.analyze(
        params=base,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
    )

    edge_only = DiameterDetectionParams(
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        window_rows_odd=1,
        stride=1,
        max_edge_shift_um_on=True,
        max_diameter_change_um_on=False,
        max_center_shift_um_on=False,
        max_edge_shift_um=0.001,
    )
    constrained = analyzer.analyze(
        params=edge_only,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
    )
    assert any(r.qc_edge_violation for r in constrained)
    assert all(not r.qc_diameter_violation for r in constrained)
    assert all(not r.qc_center_violation for r in constrained)
    lhs = np.array([r.diameter_px for r in unconstrained], dtype=float)
    rhs = np.array([r.diameter_px for r in constrained], dtype=float)
    assert not np.array_equal(lhs, rhs, equal_nan=True)


def test_motion_constraints_function_not_called_when_all_toggles_off(monkeypatch) -> None:
    analyzer = _make_analyzer()
    params = DiameterDetectionParams(
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        window_rows_odd=1,
        stride=1,
        max_edge_shift_um_on=False,
        max_diameter_change_um_on=False,
        max_center_shift_um_on=False,
    )
    calls = {"n": 0}

    def _spy_apply_motion_constraints(*_args, **_kwargs) -> None:
        calls["n"] += 1

    monkeypatch.setattr(analyzer, "_apply_motion_constraints", _spy_apply_motion_constraints)

    _ = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
    )
    assert calls["n"] == 0
