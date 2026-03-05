from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

import numpy as np
import pytest

from diameter_analysis import (
    DiameterAnalysisBundle,
    DiameterAnalyzer,
    DiameterDetectionParams,
    WIDE_CSV_ARRAY_FIELDS,
    WIDE_CSV_REGISTRY,
    WIDE_CSV_SCALAR_FIELDS,
    WIDE_CSV_TIME_COLUMNS,
    bundle_from_wide_csv_rows,
    bundle_to_wide_csv_rows,
    load_diameter_analysis,
    save_diameter_analysis,
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


def _make_detection_params_by_run() -> dict[tuple[int, int], DiameterDetectionParams]:
    return {
        (1, 1): DiameterDetectionParams(stride=2, window_rows_odd=3, gradient_sigma=1.25),
        (2, 3): DiameterDetectionParams(stride=2, window_rows_odd=3, gradient_sigma=2.5),
    }


def _make_roi_bounds_by_run(bundle: DiameterAnalysisBundle) -> dict[tuple[int, int], tuple[int, int, int, int]]:
    out: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for run_key, results in bundle.runs.items():
        if not results:
            out[run_key] = (0, 0, 0, 0)
            continue
        n_time = max(int(r.center_row) for r in results) + 1
        out[run_key] = (0, n_time, 0, 48)
    return out


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


def test_wide_csv_roundtrip_and_column_naming() -> None:
    bundle = _make_bundle()
    header, rows = bundle_to_wide_csv_rows(bundle)
    roi_to_channel = {roi: ch for roi, ch in bundle.runs.keys()}

    assert "time_s" in header
    assert "diameter_px_roi1" in header
    assert "qc_flags_roi2" in header
    assert all("__" not in col for col in header)
    suffix_cols = [c for c in header if c != "time_s"]
    assert all(re.search(r"_roi\d+$", c) for c in suffix_cols)

    loaded = bundle_from_wide_csv_rows(header, rows, roi_to_channel=roi_to_channel)
    _assert_bundle_equivalent(loaded, bundle)


def test_wide_csv_registry_drives_header_fields() -> None:
    bundle = _make_bundle()
    header, _rows = bundle_to_wide_csv_rows(bundle)

    assert list(WIDE_CSV_TIME_COLUMNS) == ["time_s"]
    suffixes = {"roi1", "roi2"}
    for suffix in suffixes:
        for field_name in WIDE_CSV_ARRAY_FIELDS:
            assert f"{field_name}_{suffix}" in header
    assert len(WIDE_CSV_SCALAR_FIELDS) == 0


def test_wide_csv_registry_columns_snapshot_single_run() -> None:
    cols = WIDE_CSV_REGISTRY.columns([(1, 1)], include_time=True, include_qc=True)
    expected = ["time_s"] + [f"{field}_roi1" for field in WIDE_CSV_ARRAY_FIELDS]
    assert cols == expected


def test_wide_csv_export_requires_include_time_true() -> None:
    bundle = _make_bundle()
    with pytest.raises(ValueError, match="include_time=True"):
        _ = bundle_to_wide_csv_rows(bundle, include_time=False)


def test_wide_csv_loader_fails_when_time_column_missing() -> None:
    bundle = _make_bundle()
    roi_to_channel = {roi: ch for roi, ch in bundle.runs.keys()}
    header, rows = bundle_to_wide_csv_rows(bundle)
    time_idx = header.index("time_s")
    bad_header = [c for i, c in enumerate(header) if i != time_idx]
    bad_rows = [[v for i, v in enumerate(r) if i != time_idx] for r in rows]
    with pytest.raises(ValueError, match="required time column: time_s"):
        _ = bundle_from_wide_csv_rows(bad_header, bad_rows, roi_to_channel=roi_to_channel)


def test_wide_csv_loader_fails_when_required_run_field_missing() -> None:
    bundle = _make_bundle()
    roi_to_channel = {roi: ch for roi, ch in bundle.runs.keys()}
    header, rows = bundle_to_wide_csv_rows(bundle)
    target = "diameter_px_roi1"
    col_idx = header.index(target)
    bad_header = [c for i, c in enumerate(header) if i != col_idx]
    bad_rows = [[v for i, v in enumerate(r) if i != col_idx] for r in rows]
    with pytest.raises(ValueError, match="missing required wide CSV column: diameter_px"):
        _ = bundle_from_wide_csv_rows(bad_header, bad_rows, roi_to_channel=roi_to_channel)


def test_wide_csv_loader_rejects_unknown_wide_field() -> None:
    bundle = _make_bundle()
    roi_to_channel = {roi: ch for roi, ch in bundle.runs.keys()}
    header, rows = bundle_to_wide_csv_rows(bundle)
    idx = header.index("qc_score_roi1") + 1
    bad_header = list(header)
    bad_header.insert(idx, "bogus_field_roi1")
    bad_rows = [list(r[:idx]) + [""] + list(r[idx:]) for r in rows]
    with pytest.raises(ValueError, match="Unknown wide CSV columns: bogus_field_roi1"):
        _ = bundle_from_wide_csv_rows(bad_header, bad_rows, roi_to_channel=roi_to_channel)


def test_wide_csv_loader_ignores_unrelated_non_wide_columns() -> None:
    bundle = _make_bundle()
    roi_to_channel = {roi: ch for roi, ch in bundle.runs.keys()}
    header, rows = bundle_to_wide_csv_rows(bundle)
    idx = header.index("time_s") + 1
    extra_header = list(header)
    extra_header.insert(idx, "notes")
    extra_rows = [list(r[:idx]) + ["x"] + list(r[idx:]) for r in rows]
    loaded = bundle_from_wide_csv_rows(extra_header, extra_rows, roi_to_channel=roi_to_channel)
    _assert_bundle_equivalent(loaded, bundle)


def test_wide_csv_loader_fails_on_malformed_roi_channel_column_name() -> None:
    bundle = _make_bundle()
    roi_to_channel = {roi: ch for roi, ch in bundle.runs.keys()}
    header, rows = bundle_to_wide_csv_rows(bundle)
    idx = header.index("diameter_px_roi1") + 1
    bad_header = list(header)
    bad_header.insert(idx, "diameter_px_roiX")
    bad_rows = [list(r[:idx]) + [""] + list(r[idx:]) for r in rows]
    with pytest.raises(ValueError, match="Invalid wide CSV column name: 'diameter_px_roiX'"):
        _ = bundle_from_wide_csv_rows(bad_header, bad_rows, roi_to_channel=roi_to_channel)


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


def test_save_load_diameter_analysis_roundtrip_sidecars(tmp_path: Path) -> None:
    bundle = _make_bundle()
    params_by_run = _make_detection_params_by_run()
    roi_bounds_by_run = _make_roi_bounds_by_run(bundle)
    kym_path = tmp_path / "sample_kym.tif"

    json_path, csv_path = save_diameter_analysis(
        kym_path,
        bundle,
        roi_bounds_by_run=roi_bounds_by_run,
        detection_params_by_run=params_by_run,
    )
    assert json_path.name == "sample_kym.diameter.json"
    assert csv_path.name == "sample_kym.diameter.csv"
    assert json_path.parent == tmp_path
    assert csv_path.parent == tmp_path

    loaded, loaded_params_by_run, loaded_bounds_by_run, _warnings = load_diameter_analysis(kym_path)
    _assert_bundle_equivalent(loaded, bundle)
    assert loaded_params_by_run == params_by_run
    assert loaded_bounds_by_run == roi_bounds_by_run
    for run_key in sorted(bundle.runs):
        base = bundle.runs[run_key]
        got = loaded.runs[run_key]
        assert len(base) == len(got)
        for left, right in zip(base, got):
            assert np.isclose(right.sum_intensity, left.sum_intensity, equal_nan=True)


def test_load_diameter_analysis_fails_when_run_required_key_missing(tmp_path: Path) -> None:
    bundle = _make_bundle()
    params_by_run = _make_detection_params_by_run()
    roi_bounds_by_run = _make_roi_bounds_by_run(bundle)
    kym_path = tmp_path / "sample_kym.tif"
    json_path, _csv_path = save_diameter_analysis(
        kym_path,
        bundle,
        roi_bounds_by_run=roi_bounds_by_run,
        detection_params_by_run=params_by_run,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    del payload["rois"]["1"]["channel_id"]
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required key: channel_id"):
        _ = load_diameter_analysis(kym_path)


def test_load_diameter_analysis_tolerates_extra_json_and_csv_columns(tmp_path: Path) -> None:
    bundle = _make_bundle()
    params_by_run = _make_detection_params_by_run()
    roi_bounds_by_run = _make_roi_bounds_by_run(bundle)
    kym_path = tmp_path / "sample_kym.tif"
    json_path, csv_path = save_diameter_analysis(
        kym_path,
        bundle,
        roi_bounds_by_run=roi_bounds_by_run,
        detection_params_by_run=params_by_run,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    payload["extra_json_note"] = "ok"
    payload["rois"]["1"]["extra_run_field"] = "ok"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    rows[0].append("notes")
    for idx in range(1, len(rows)):
        rows[idx].append(f"row-{idx}")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    loaded, loaded_params_by_run, loaded_bounds_by_run, _warnings = load_diameter_analysis(kym_path)
    _assert_bundle_equivalent(loaded, bundle)
    assert loaded_params_by_run == params_by_run
    assert loaded_bounds_by_run == roi_bounds_by_run


def test_wide_csv_contains_sum_intensity_and_um_columns() -> None:
    bundle = _make_bundle()
    header, rows = bundle_to_wide_csv_rows(bundle)
    assert "sum_intensity_roi1" in header
    assert "left_edge_um_roi1" in header
    assert "right_edge_um_roi1" in header
    assert "diameter_um_roi1" in header

    run = bundle.runs[(1, 1)]
    row0 = rows[0]
    col = {name: i for i, name in enumerate(header)}
    r0 = run[0]
    assert np.isclose(float(row0[col["left_edge_um_roi1"]]), r0.left_edge_px * r0.um_per_pixel)
    assert np.isclose(float(row0[col["right_edge_um_roi1"]]), r0.right_edge_px * r0.um_per_pixel)
    assert np.isclose(float(row0[col["diameter_um_roi1"]]), r0.diameter_px * r0.um_per_pixel)
    assert np.isclose(float(row0[col["sum_intensity_roi1"]]), r0.sum_intensity)


def test_sum_intensity_matches_binned_profile_sum() -> None:
    payload = generate_synthetic_kymograph(n_time=40, n_space=48, seed=17)
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(stride=2, window_rows_odd=3)
    results = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
    )
    r0 = results[0]
    half = params.window_rows_odd // 2
    w0 = max(0, r0.center_row - half)
    w1 = min(analyzer.kymograph.shape[0], r0.center_row + half + 1)
    window = analyzer.kymograph[w0:w1, :]
    if params.binning_method.value == "mean":
        profile = np.nanmean(window, axis=0)
    else:
        profile = np.nanmedian(window, axis=0)
    profile_proc = np.asarray(profile, dtype=float)
    if params.polarity.value == "dark_on_bright":
        profile_proc = np.nanmax(profile_proc) - profile_proc
    expected = float(np.sum(profile_proc))
    assert np.isclose(r0.sum_intensity, expected)


def test_sidecar_json_does_not_store_sum_intensity(tmp_path: Path) -> None:
    bundle = _make_bundle()
    params_by_run = _make_detection_params_by_run()
    roi_bounds_by_run = _make_roi_bounds_by_run(bundle)
    kym_path = tmp_path / "sample_kym.tif"
    json_path, _csv_path = save_diameter_analysis(
        kym_path,
        bundle,
        roi_bounds_by_run=roi_bounds_by_run,
        detection_params_by_run=params_by_run,
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    for roi_payload in payload["rois"].values():
        assert "results" not in roi_payload


def test_load_diameter_analysis_fails_when_detection_params_missing(tmp_path: Path) -> None:
    bundle = _make_bundle()
    params_by_run = _make_detection_params_by_run()
    roi_bounds_by_run = _make_roi_bounds_by_run(bundle)
    kym_path = tmp_path / "sample_kym.tif"
    json_path, _csv_path = save_diameter_analysis(
        kym_path,
        bundle,
        roi_bounds_by_run=roi_bounds_by_run,
        detection_params_by_run=params_by_run,
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    del payload["rois"]["1"]["detection_params"]
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required key: detection_params"):
        _ = load_diameter_analysis(kym_path)
