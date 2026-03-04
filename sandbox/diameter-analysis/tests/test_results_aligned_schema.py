from __future__ import annotations

import pytest

from diameter_analysis import (
    ALIGNED_RESULTS_SCHEMA_VERSION,
    DiameterAlignedResults,
    DiameterAnalyzer,
    DiameterDetectionParams,
    DiameterResult,
    DiameterMethod,
)
from synthetic_kymograph import generate_synthetic_kymograph


def test_aligned_results_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length=1 does not match diameter_um length=2"):
        DiameterAlignedResults(
            schema_version=ALIGNED_RESULTS_SCHEMA_VERSION,
            source="synthetic",
            path=None,
            roi_id=None,
            channel_id=None,
            seconds_per_line=0.01,
            um_per_pixel=0.2,
            time_s=[0.0, 0.01],
            left_um=[1.0, 2.0],
            right_um=[3.0, 4.0],
            center_um=[2.0, 3.0],
            diameter_um=[2.0, 2.0],
            diameter_um_filtered=None,
            qc_left_edge_violation=[False],
            qc_right_edge_violation=[False, False],
            qc_center_shift_violation=[False, False],
            qc_diameter_change_violation=[False, False],
        )


def test_aligned_results_roundtrip_preserves_none() -> None:
    obj = DiameterAlignedResults(
        schema_version=ALIGNED_RESULTS_SCHEMA_VERSION,
        source="real",
        path="/tmp/fake.tif",
        roi_id=1,
        channel_id=1,
        seconds_per_line=0.01,
        um_per_pixel=0.25,
        time_s=[0.0, 0.01, 0.02],
        left_um=[1.0, None, 1.5],
        right_um=[4.0, None, 4.5],
        center_um=[2.5, None, 3.0],
        diameter_um=[3.0, None, 3.0],
        diameter_um_filtered=[3.0, None, 2.9],
        qc_left_edge_violation=[False, True, False],
        qc_right_edge_violation=[False, True, False],
        qc_center_shift_violation=[False, False, False],
        qc_diameter_change_violation=[False, True, False],
    )
    payload = obj.to_dict()
    reloaded = DiameterAlignedResults.from_dict(payload)
    assert reloaded == obj
    assert reloaded.diameter_um[1] is None
    assert reloaded.left_um[1] is None
    assert reloaded.qc_any_violation == [False, True, False]


def test_qc_flags_aligned_with_trace_length() -> None:
    payload = generate_synthetic_kymograph(n_time=80, n_space=96, seed=13)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(
        diameter_method=DiameterMethod.GRADIENT_EDGES,
        window_rows_odd=1,
        stride=1,
        enable_motion_constraints=True,
        max_edge_shift_um=0.001,
        max_diameter_change_um=0.001,
        max_center_shift_um=0.001,
    )
    aligned = analyzer.analyze_aligned(params=params, source="synthetic")

    n = len(aligned.diameter_um)
    assert n > 0
    assert len(aligned.left_um) == n
    assert len(aligned.right_um) == n
    assert len(aligned.center_um) == n
    assert len(aligned.qc_left_edge_violation) == n
    assert len(aligned.qc_right_edge_violation) == n
    assert len(aligned.qc_center_shift_violation) == n
    assert len(aligned.qc_diameter_change_violation) == n
    assert len(aligned.qc_any_violation or []) == n


def test_diameter_result_row_roundtrip() -> None:
    result = DiameterResult(
        center_row=4,
        time_s=0.2,
        left_edge_px=11.0,
        right_edge_px=18.0,
        diameter_px=7.0,
        peak=0.9,
        baseline=0.1,
        edge_strength_left=0.2,
        edge_strength_right=0.25,
        diameter_px_filt=6.5,
        diameter_was_filtered=True,
        qc_score=0.8,
        qc_flags=["gradient_low_edge_strength"],
        qc_edge_violation=False,
        qc_diameter_violation=True,
        qc_center_violation=False,
    )
    row = result.to_row(roi_id=1, schema_version=1, um_per_pixel=0.4)
    loaded = DiameterResult.from_row({k: str(v) for k, v in row.items()})
    assert loaded == result
