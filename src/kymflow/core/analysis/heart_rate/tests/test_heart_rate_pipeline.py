import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import kymflow.core.analysis.heart_rate.heart_rate_pipeline as hrp
from kymflow.core.analysis.heart_rate.heart_rate_analysis import (
    HRStatus,
    HeartRateEstimate,
    estimate_heart_rate_global,
)


def _write_csv(tmp_path, df: pd.DataFrame, name: str = "sample.csv"):
    path = tmp_path / name
    df.to_csv(path, index=False)
    return path


def _fake_estimator(time_s, velocity, *, method, **kwargs):
    t = np.asarray(time_s, dtype=float)
    finite = np.isfinite(t)
    n = int(t.size)
    n_valid = int(np.sum(finite))
    if method == "lombscargle":
        est = HeartRateEstimate(
            bpm=420.0,
            f_hz=7.0,
            t_start=float(np.nanmin(t[finite])) if n_valid else 0.0,
            t_end=float(np.nanmax(t[finite])) if n_valid else 0.0,
            n_samples=n,
            n_valid=n_valid,
            snr=3.0,
            method="lombscargle",
        )
        return est, {"f_grid": [6.5, 7.0, 7.5], "power": [0.1, 1.0, 0.1]}

    est = HeartRateEstimate(
        bpm=426.0,
        f_hz=7.1,
        t_start=float(np.nanmin(t[finite])) if n_valid else 0.0,
        t_end=float(np.nanmax(t[finite])) if n_valid else 0.0,
        n_samples=n,
        n_valid=n_valid,
        snr=2.5,
        method="welch",
    )
    return est, {"f": [6.8, 7.1, 7.4], "Pxx": [0.2, 0.9, 0.2]}


def test_from_csv_raises_when_roi_missing(tmp_path):
    df = pd.DataFrame(
        {
            "time": [0.0, 0.01, 0.02],
            "velocity": [1.0, 1.1, 1.2],
        }
    )
    csv_path = _write_csv(tmp_path, df, name="no_roi.csv")

    with pytest.raises(ValueError, match="roi"):
        hrp.HeartRateAnalysis.from_csv(csv_path)


def test_from_csv_loads_df_and_roi_ids(tmp_path):
    df = pd.DataFrame(
        {
            "time": [0.0, 0.01, 0.02, 0.03],
            "velocity": [1.0, 1.1, 1.2, 1.3],
            "roi_id": [2, 1, 2, 1],
        }
    )
    csv_path = _write_csv(tmp_path, df)
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)

    assert list(analysis.df.columns) == ["time", "velocity", "roi_id"]
    assert analysis.roi_ids == [1, 2]


def test_run_roi_stores_results_and_config(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)

    t = np.linspace(0, 4, 401)
    v = np.sin(2 * np.pi * 7 * t)
    df = pd.DataFrame(
        {
            "time": np.concatenate([t, t]),
            "velocity": np.concatenate([v, v]),
            "roi_id": np.concatenate([np.full_like(t, 1, dtype=int), np.full_like(t, 2, dtype=int)]),
        }
    )
    csv_path = _write_csv(tmp_path, df)
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)

    cfg = {"bpm_band": (200, 700), "use_abs": False, "lomb_n_freq": 256}
    result = analysis.run_roi(1, cfg=cfg)

    assert 1 in analysis.results_by_roi
    assert not hasattr(analysis, "cfg_by_roi")
    assert result.lomb is not None and result.lomb.bpm == 420.0
    assert result.welch is not None and result.welch.bpm == 426.0
    assert result.analysis_cfg.bpm_band == (200, 700)
    assert result.analysis_cfg.use_abs is False


def test_run_all_rois_uses_cfg_by_roi(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)

    t = np.linspace(0, 4, 401)
    v = np.sin(2 * np.pi * 7 * t)
    df = pd.DataFrame(
        {
            "time": np.concatenate([t, t]),
            "velocity": np.concatenate([v, v]),
            "roi_id": np.concatenate([np.full_like(t, 1, dtype=int), np.full_like(t, 2, dtype=int)]),
        }
    )
    csv_path = _write_csv(tmp_path, df)
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)

    analysis.run_all_rois(
        cfg_by_roi={
            1: {"bpm_band": (250, 500), "lomb_n_freq": 111},
            2: {"bpm_band": (300, 650), "lomb_n_freq": 222},
        }
    )

    assert analysis.results_by_roi[1].analysis_cfg.bpm_band == (250, 500)
    assert analysis.results_by_roi[1].analysis_cfg.lomb_n_freq == 111
    assert analysis.results_by_roi[2].analysis_cfg.bpm_band == (300, 650)
    assert analysis.results_by_roi[2].analysis_cfg.lomb_n_freq == 222


def test_get_summary_dict_json_serializable_and_contains_config(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)

    t = np.linspace(0, 4, 401)
    v = np.sin(2 * np.pi * 7 * t)
    df = pd.DataFrame(
        {
            "time": np.concatenate([t, t]),
            "velocity": np.concatenate([v, v]),
            "roi_id": np.concatenate([np.full_like(t, 1, dtype=int), np.full_like(t, 2, dtype=int)]),
        }
    )
    csv_path = _write_csv(tmp_path, df)

    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)
    analysis.run_all_rois(cfg={"bpm_band": (240, 600)})

    summary = analysis.getSummaryDict()
    encoded = json.dumps(summary)

    assert encoded
    assert "per_roi" in summary
    assert "1" in summary["per_roi"]
    assert "2" in summary["per_roi"]
    assert "analysis_cfg" in summary["per_roi"]["1"]
    assert summary["per_roi"]["1"]["analysis_cfg"]["bpm_band"] == [240.0, 600.0]


def test_qc_metrics_keys_present_in_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)

    t = np.linspace(0, 4, 401)
    v = np.sin(2 * np.pi * 7 * t)
    df = pd.DataFrame(
        {
            "time": np.concatenate([t, t]),
            "velocity": np.concatenate([v, v]),
            "roi_id": np.concatenate([np.full_like(t, 1, dtype=int), np.full_like(t, 2, dtype=int)]),
        }
    )
    csv_path = _write_csv(tmp_path, df)
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)
    analysis.run_roi(1, cfg={"do_segments": False})
    summary = analysis.getSummaryDict()

    lomb = summary["per_roi"]["1"]["lomb"]
    welch = summary["per_roi"]["1"]["welch"]
    for payload in (lomb, welch):
        assert "edge_flag" in payload
        assert "edge_hz_distance" in payload
        assert "band_concentration" in payload


def test_edge_flag_true_for_peak_near_band_edge():
    fs = 100.0
    t = np.arange(0.0, 20.0, 1.0 / fs)
    v = np.sin(2.0 * np.pi * 4.0 * t)  # exactly at lower edge for 240 bpm

    est, dbg = estimate_heart_rate_global(
        t,
        v,
        bpm_band=(240.0, 600.0),
        use_abs=False,
        method="lombscargle",
        lomb_n_freq=2048,
    )
    assert est is not None
    assert est.edge_flag is True
    assert isinstance(est.edge_hz_distance, float)
    assert "edge_flag" in dbg


def test_segments_respect_do_segments_flag(tmp_path):
    fs = 100.0
    t = np.arange(0.0, 30.0, 1.0 / fs)
    v = np.sin(2.0 * np.pi * 7.0 * t)
    df = pd.DataFrame(
        {
            "time": np.concatenate([t, t]),
            "velocity": np.concatenate([v, v]),
            "roi_id": np.concatenate([np.full_like(t, 1, dtype=int), np.full_like(t, 2, dtype=int)]),
        }
    )
    csv_path = _write_csv(tmp_path, df)
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)

    r_no_seg = analysis.run_roi(1, cfg={"do_segments": False})
    assert r_no_seg.segments is None

    r_seg = analysis.run_roi(
        1,
        cfg={
            "do_segments": True,
            "seg_win_sec": 6.0,
            "seg_step_sec": 1.0,
            "seg_min_valid_frac": 0.5,
        },
    )
    assert r_seg.segments is not None
    n_win = len(r_seg.segments["t_center"])
    assert n_win > 0
    assert len(r_seg.segments["bpm"]) == n_win
    assert len(r_seg.segments["snr"]) == n_win
    assert len(r_seg.segments["valid_frac"]) == n_win


def test_summary_compact_excludes_raw_segments_and_includes_segment_summary(tmp_path):
    fs = 100.0
    t = np.arange(0.0, 30.0, 1.0 / fs)
    v = np.sin(2.0 * np.pi * 7.0 * t)
    df = pd.DataFrame(
        {
            "time": np.concatenate([t, t]),
            "velocity": np.concatenate([v, v]),
            "roi_id": np.concatenate([np.full_like(t, 1, dtype=int), np.full_like(t, 2, dtype=int)]),
        }
    )
    csv_path = _write_csv(tmp_path, df)
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)
    analysis.run_roi(1, cfg={"do_segments": True, "seg_win_sec": 6.0, "seg_step_sec": 1.0})

    compact = analysis.getSummaryDict(compact=True)["per_roi"]["1"]
    full = analysis.getSummaryDict(compact=False)["per_roi"]["1"]

    assert "analysis_cfg" in compact
    assert "segments_summary" in compact
    assert "segments" not in compact
    assert "n_windows" in compact["segments_summary"]
    assert "segments" in full
    assert isinstance(full["segments"], dict)


def test_helper_methods_get_roi_df_time_velocity_results_and_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)
    t = np.linspace(0, 4, 401)
    v = np.sin(2 * np.pi * 7 * t)
    df = pd.DataFrame(
        {
            "time": np.concatenate([t[::-1], t]),
            "velocity": np.concatenate([v[::-1], v]),
            "roi_id": np.concatenate([np.full_like(t, 1, dtype=int), np.full_like(t, 2, dtype=int)]),
        }
    )
    csv_path = _write_csv(tmp_path, df)
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)
    analysis.run_roi(1, cfg={"do_segments": False})

    roi_df = analysis.get_roi_df(1)
    assert not roi_df.empty
    tt, vv = analysis.get_time_velocity(1)
    assert tt.size == vv.size
    assert np.all(np.diff(tt) >= 0)
    rr = analysis.get_roi_results(1)
    assert rr.roi_id == 1
    smin = analysis.get_roi_summary(1, minimal=True)
    assert "status" in smin and "lomb_bpm" in smin and "welch_bpm" in smin
    assert "file" in smin and "agree_ok" in smin


def test_minimal_summary_has_expected_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)
    t = np.linspace(0, 4, 401)
    v = np.sin(2 * np.pi * 7 * t)
    df = pd.DataFrame({"time": t, "velocity": v, "roi_id": np.ones_like(t, dtype=int)})
    csv_path = _write_csv(tmp_path, df)
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)
    analysis.run_roi(1)

    summary = analysis.get_roi_summary(1, minimal=True)
    expected_keys = {
        "file",
        "roi_id",
        "n_total",
        "n_valid",
        "valid_frac",
        "t_min",
        "t_max",
        "lomb_bpm",
        "lomb_hz",
        "lomb_snr",
        "welch_bpm",
        "welch_hz",
        "welch_snr",
        "lomb_edge",
        "welch_edge",
        "lomb_bc",
        "welch_bc",
        "agree_delta_bpm",
        "agree_ok",
        "status",
        "status_note",
    }
    assert expected_keys.issubset(set(summary.keys()))
    assert summary["status"] in {s.value for s in HRStatus}


def test_status_insufficient_valid_for_too_few_samples(tmp_path):
    t = np.linspace(0, 1, 100)
    v = np.sin(2 * np.pi * 7 * t)
    df = pd.DataFrame({"time": t, "velocity": v, "roi_id": np.ones_like(t, dtype=int)})
    csv_path = _write_csv(tmp_path, df)
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)
    analysis.run_roi(1)
    s = analysis.get_roi_summary(1, minimal=True)
    assert s["status"] == "insufficient_valid"


def test_status_method_disagree_when_methods_far_apart(tmp_path, monkeypatch):
    def _disagree_estimator(time_s, velocity, *, method, **kwargs):
        tloc = np.asarray(time_s, dtype=float)
        n = int(tloc.size)
        if method == "lombscargle":
            est = HeartRateEstimate(
                bpm=300.0,
                f_hz=5.0,
                t_start=float(np.nanmin(tloc)),
                t_end=float(np.nanmax(tloc)),
                n_samples=n,
                n_valid=n,
                snr=2.0,
                method="lombscargle",
            )
            return est, {}
        est = HeartRateEstimate(
            bpm=450.0,
            f_hz=7.5,
            t_start=float(np.nanmin(tloc)),
            t_end=float(np.nanmax(tloc)),
            n_samples=n,
            n_valid=n,
            snr=2.0,
            method="welch",
        )
        return est, {}

    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _disagree_estimator)
    t = np.linspace(0, 10, 1000)
    v = np.sin(2 * np.pi * 7 * t)
    df = pd.DataFrame({"time": t, "velocity": v, "roi_id": np.ones_like(t, dtype=int)})
    csv_path = _write_csv(tmp_path, df)
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)
    analysis.run_roi(1)
    s = analysis.get_roi_summary(1, minimal=True)
    assert s["status"] == "method_disagree"
    assert s["agree_ok"] is False


def test_mini_summary_exact_keys_and_status_note_policy(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)
    t = np.linspace(0, 4, 401)
    v = np.sin(2 * np.pi * 7 * t)
    df = pd.DataFrame({"time": t, "velocity": v, "roi_id": np.ones_like(t, dtype=int)})
    csv_path = _write_csv(tmp_path, df, name="abc.csv")
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)
    analysis.run_roi(1)

    mini = analysis.get_roi_summary(1, minimal="mini")
    assert set(mini.keys()) == {
        "file",
        "roi_id",
        "valid_frac",
        "lomb_bpm",
        "lomb_hz",
        "lomb_snr",
        "welch_bpm",
        "welch_hz",
        "welch_snr",
        "agree_delta_bpm",
        "agree_ok",
        "status",
        "status_note",
    }
    assert mini["file"] == "abc.csv"
    assert mini["status"] == HRStatus.OK.value
    assert mini["status_note"] == ""


def test_mini_summary_adds_status_note_when_non_ok(tmp_path):
    t = np.linspace(0, 1, 100)
    v = np.sin(2 * np.pi * 7 * t)
    df = pd.DataFrame({"time": t, "velocity": v, "roi_id": np.ones_like(t, dtype=int)})
    csv_path = _write_csv(tmp_path, df, name="bad.csv")
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)
    analysis.run_roi(1)

    mini = analysis.get_roi_summary(1, minimal="mini")
    assert mini["status"] == HRStatus.INSUFFICIENT_VALID.value
    assert "lomb_hz" in mini and "welch_hz" in mini
    assert "status_note" in mini
    assert isinstance(mini["status_note"], str)


def test_status_not_inferred_from_reason_substrings(tmp_path, monkeypatch):
    def _substring_trap_estimator(time_s, velocity, *, method, **kwargs):
        tloc = np.asarray(time_s, dtype=float)
        n = int(tloc.size)
        if method == "lombscargle":
            est = HeartRateEstimate(
                bpm=420.0,
                f_hz=7.0,
                t_start=float(np.nanmin(tloc)),
                t_end=float(np.nanmax(tloc)),
                n_samples=n,
                n_valid=n,
                snr=2.0,
                method="lombscargle",
            )
            return est, {"status": HRStatus.OK.value, "note": ""}
        return None, {
            "status": HRStatus.OTHER_ERROR.value,
            "reason": "contains no_peak_welch substring but should not control status",
            "note": "welch failed for unrelated reason",
        }

    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _substring_trap_estimator)
    t = np.linspace(0, 10, 1000)
    v = np.sin(2 * np.pi * 7 * t)
    df = pd.DataFrame({"time": t, "velocity": v, "roi_id": np.ones_like(t, dtype=int)})
    csv_path = _write_csv(tmp_path, df)
    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)
    analysis.run_roi(1)

    s = analysis.get_roi_summary(1, minimal=True)
    assert s["status"] == HRStatus.OK.value


def test_runner_no_argparse_dependency():
    runner_path = Path(__file__).resolve().parents[1] / "run_heart_rate_examples_fixed2.py"
    text = runner_path.read_text(encoding="utf-8")
    assert "import argparse" not in text
    assert "def parse_args" not in text
