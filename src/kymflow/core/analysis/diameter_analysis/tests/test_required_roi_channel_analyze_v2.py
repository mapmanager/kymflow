from __future__ import annotations

import csv

import pytest

from kymflow.core.analysis.diameter_analysis import (
    DiameterAnalyzer,
    DiameterDetectionParams,
    DiameterResult,
    generate_synthetic_kymograph,
)
from kymflow.core.analysis.diameter_analysis.diameter_analysis import (
    DiameterAnalysisBundle,
    load_diameter_analysis,
    save_diameter_analysis,
)


def _make_analyzer() -> DiameterAnalyzer:
    payload = generate_synthetic_kymograph(n_time=32, n_space=40, seed=7)
    return DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )


def test_analyze_requires_roi_and_channel_keyword_args() -> None:
    analyzer = _make_analyzer()

    with pytest.raises(TypeError):
        analyzer.analyze()  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        analyzer.analyze(  # type: ignore[call-arg]
            params=DiameterDetectionParams(),
            roi_id=1,
            channel_id=1,
        )


def test_analyze_rejects_invalid_roi_bounds() -> None:
    analyzer = _make_analyzer()

    with pytest.raises(ValueError, match="roi time bounds"):
        analyzer.analyze(
            params=DiameterDetectionParams(),
            roi_id=1,
            roi_bounds=(-1, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
            channel_id=1,
        )

    with pytest.raises(ValueError, match="roi space bounds"):
        analyzer.analyze(
            params=DiameterDetectionParams(),
            roi_id=1,
            roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1] + 1),
            channel_id=1,
        )


def test_save_load_roundtrip_preserves_roi_and_channel_ids(tmp_path) -> None:
    analyzer = _make_analyzer()
    params = DiameterDetectionParams(stride=2, window_rows_odd=3)
    roi_id = 7
    channel_id = 3
    results = analyzer.analyze(
        params=params,
        roi_id=roi_id,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=channel_id,
    )

    kym_path = tmp_path / "ids.tif"
    save_diameter_analysis(
        kym_path,
        DiameterAnalysisBundle(runs={(roi_id, channel_id): results}),
        roi_bounds_by_run={
            (roi_id, channel_id): (0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1])
        },
        detection_params_by_run={(roi_id, channel_id): params},
    )

    csv_path = tmp_path / "ids.diameter.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert f"diameter_px_roi{roi_id}" in rows[0]

    loaded_bundle, _params, _bounds, warnings = load_diameter_analysis(kym_path)
    assert warnings == []
    loaded_results = loaded_bundle.runs[(roi_id, channel_id)]
    assert loaded_results
    assert all(r.roi_id == roi_id for r in loaded_results)
    assert all(r.channel_id == channel_id for r in loaded_results)


def test_diameter_result_requires_roi_and_channel_at_construction() -> None:
    with pytest.raises(TypeError):
        DiameterResult(  # type: ignore[call-arg]
            center_row=1,
            time_s=0.1,
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
        )


def test_diameter_result_rejects_non_int_roi_or_channel() -> None:
    with pytest.raises(ValueError, match="roi_id must be int"):
        DiameterResult(  # type: ignore[arg-type]
            roi_id="1",
            channel_id=1,
            center_row=1,
            time_s=0.1,
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
        )

    with pytest.raises(ValueError, match="channel_id must be int"):
        DiameterResult(  # type: ignore[arg-type]
            roi_id=1,
            channel_id="1",
            center_row=1,
            time_s=0.1,
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
        )


def test_from_row_raises_when_roi_or_channel_missing() -> None:
    row = {
        "roi_id": "1",
        "channel_id": "1",
        "center_row": "4",
        "time_s": "0.2",
        "left_edge_px": "11.0",
        "right_edge_px": "18.0",
        "diameter_px": "7.0",
        "peak": "0.9",
        "baseline": "0.1",
        "edge_strength_left": "0.2",
        "edge_strength_right": "0.25",
        "diameter_px_filt": "6.5",
        "diameter_was_filtered": "1",
        "qc_score": "0.8",
        "qc_flags": "gradient_low_edge_strength",
        "qc_edge_violation": "0",
        "qc_diameter_violation": "1",
        "qc_center_violation": "0",
    }

    missing_roi = dict(row)
    missing_roi.pop("roi_id")
    with pytest.raises(ValueError, match="Missing required row key: roi_id"):
        DiameterResult.from_row(missing_roi)

    missing_channel = dict(row)
    missing_channel.pop("channel_id")
    with pytest.raises(ValueError, match="Missing required row key: channel_id"):
        DiameterResult.from_row(missing_channel)


def test_from_row_fails_fast_when_required_non_id_field_missing() -> None:
    row = {
        "roi_id": "1",
        "channel_id": "1",
        "center_row": "4",
        "time_s": "0.2",
        "left_edge_px": "11.0",
        "right_edge_px": "18.0",
        "diameter_px": "7.0",
        "peak": "0.9",
        "baseline": "0.1",
        "edge_strength_left": "0.2",
        "edge_strength_right": "0.25",
        "diameter_px_filt": "6.5",
        "diameter_was_filtered": "1",
        "qc_score": "0.8",
        "qc_flags": "",
        "qc_edge_violation": "0",
        "qc_diameter_violation": "1",
        "qc_center_violation": "0",
    }

    bad = dict(row)
    bad.pop("edge_strength_left")
    with pytest.raises(ValueError, match="Missing required row key: edge_strength_left"):
        DiameterResult.from_row(bad)


def test_from_dict_rejects_string_roi_id() -> None:
    payload = {
        "roi_id": "1",
        "channel_id": 1,
        "center_row": 4,
        "time_s": 0.2,
        "left_edge_px": 11.0,
        "right_edge_px": 18.0,
        "diameter_px": 7.0,
        "peak": 0.9,
        "baseline": 0.1,
        "edge_strength_left": 0.2,
        "edge_strength_right": 0.25,
        "diameter_px_filt": 6.5,
        "diameter_was_filtered": True,
        "qc_score": 0.8,
        "qc_flags": [],
        "qc_edge_violation": False,
        "qc_diameter_violation": True,
        "qc_center_violation": False,
    }
    with pytest.raises(ValueError, match="roi_id must be int"):
        DiameterResult.from_dict(payload)  # type: ignore[arg-type]
