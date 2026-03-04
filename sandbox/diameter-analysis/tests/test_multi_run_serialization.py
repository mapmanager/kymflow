from __future__ import annotations

import json
import math
import re

from diameter_analysis import (
    DiameterAnalysisBundle,
    DiameterAnalyzer,
    DiameterDetectionParams,
    bundle_from_wide_csv_rows,
    bundle_to_wide_csv_rows,
)
from synthetic_kymograph import generate_synthetic_kymograph


def _make_bundle() -> DiameterAnalysisBundle:
    payload = generate_synthetic_kymograph(n_time=40, n_space=48, seed=17)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(stride=2, window_rows_odd=3)

    run_a = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
    )
    run_b = analyzer.analyze(
        params=params,
        roi_id=2,
        roi_bounds=(4, analyzer.kymograph.shape[0] - 2, 2, analyzer.kymograph.shape[1] - 2),
        channel_id=3,
    )
    return DiameterAnalysisBundle(runs={(1, 1): run_a, (2, 3): run_b})


def _assert_bundle_equivalent(lhs: DiameterAnalysisBundle, rhs: DiameterAnalysisBundle) -> None:
    assert lhs.schema_version == rhs.schema_version
    assert sorted(lhs.runs.keys()) == sorted(rhs.runs.keys())
    for run_key in sorted(lhs.runs.keys()):
        left_results = lhs.runs[run_key]
        right_results = rhs.runs[run_key]
        assert len(left_results) == len(right_results)
        for left, right in zip(left_results, right_results):
            assert left.roi_id == right.roi_id
            assert left.channel_id == right.channel_id
            assert left.center_row == right.center_row
            assert left.time_s == right.time_s
            assert left.left_edge_px == right.left_edge_px
            assert left.right_edge_px == right.right_edge_px
            assert left.diameter_px == right.diameter_px
            assert left.peak == right.peak
            assert left.baseline == right.baseline
            if math.isnan(left.edge_strength_left):
                assert math.isnan(right.edge_strength_left)
            else:
                assert left.edge_strength_left == right.edge_strength_left
            if math.isnan(left.edge_strength_right):
                assert math.isnan(right.edge_strength_right)
            else:
                assert left.edge_strength_right == right.edge_strength_right
            assert left.diameter_px_filt == right.diameter_px_filt
            assert left.diameter_was_filtered == right.diameter_was_filtered
            assert left.qc_score == right.qc_score
            assert left.qc_flags == right.qc_flags
            assert left.qc_edge_violation == right.qc_edge_violation
            assert left.qc_diameter_violation == right.qc_diameter_violation
            assert left.qc_center_violation == right.qc_center_violation


def test_bundle_json_roundtrip_two_runs() -> None:
    bundle = _make_bundle()
    payload = bundle.to_dict()
    loaded = DiameterAnalysisBundle.from_dict(json.loads(json.dumps(payload)))
    _assert_bundle_equivalent(loaded, bundle)


def test_bundle_from_dict_missing_roi_or_channel_fails_fast() -> None:
    bundle = _make_bundle()
    payload = bundle.to_dict()

    run = payload["runs"]["roi1_ch1"]
    missing_roi_payload = json.loads(json.dumps(payload))
    del missing_roi_payload["runs"]["roi1_ch1"]["roi_id"]
    try:
        DiameterAnalysisBundle.from_dict(missing_roi_payload)
        assert False, "Expected ValueError for missing roi_id"
    except ValueError as exc:
        assert "missing required key: roi_id" in str(exc)

    missing_channel_payload = json.loads(json.dumps(payload))
    del missing_channel_payload["runs"]["roi1_ch1"]["channel_id"]
    try:
        DiameterAnalysisBundle.from_dict(missing_channel_payload)
        assert False, "Expected ValueError for missing channel_id"
    except ValueError as exc:
        assert "missing required key: channel_id" in str(exc)

    assert isinstance(run, dict)


def test_wide_csv_roundtrip_and_column_naming() -> None:
    bundle = _make_bundle()
    header, rows = bundle_to_wide_csv_rows(bundle)

    assert "time_s" in header
    assert "diameter_px_roi1_ch1" in header
    assert "qc_flags_roi2_ch3" in header
    assert all("__" not in col for col in header)
    suffix_cols = [c for c in header if c != "time_s"]
    assert all(re.search(r"_roi\d+_ch\d+$", c) for c in suffix_cols)

    loaded = bundle_from_wide_csv_rows(header, rows)
    _assert_bundle_equivalent(loaded, bundle)


def test_analyze_strict_roi_channel_propagation() -> None:
    payload = generate_synthetic_kymograph(n_time=24, n_space=36, seed=9)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    results = analyzer.analyze(
        params=DiameterDetectionParams(stride=2),
        roi_id=7,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=5,
    )

    assert len(results) > 0
    assert all(r.roi_id == 7 for r in results)
    assert all(r.channel_id == 5 for r in results)
