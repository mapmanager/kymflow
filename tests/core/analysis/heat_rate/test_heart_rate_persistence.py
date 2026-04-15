import json
from pathlib import Path

import numpy as np
import pandas as pd

import kymflow.core.analysis.heart_rate.heart_rate_pipeline as hrp
from kymflow.core.analysis.heart_rate.heart_rate_analysis import HeartRateEstimate


def _fake_estimator(time_s, velocity, *, method, **kwargs):
    t = np.asarray(time_s, dtype=float)
    n = int(t.size)
    if method == "lombscargle":
        est = HeartRateEstimate(
            bpm=420.0,
            f_hz=7.0,
            t_start=float(np.nanmin(t)),
            t_end=float(np.nanmax(t)),
            n_samples=n,
            n_valid=n,
            snr=3.0,
            method="lombscargle",
        )
        return est, {"status": "ok", "note": ""}
    est = HeartRateEstimate(
        bpm=426.0,
        f_hz=7.1,
        t_start=float(np.nanmin(t)),
        t_end=float(np.nanmax(t)),
        n_samples=n,
        n_valid=n,
        snr=2.0,
        method="welch",
    )
    return est, {"status": "ok", "note": ""}


def _make_analysis(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)
    t = np.linspace(0.0, 4.0, 401)
    v = np.sin(2.0 * np.pi * 7.0 * t)
    df = pd.DataFrame({"time": t, "velocity": v, "roi_id": np.ones_like(t, dtype=int)})
    source_csv = tmp_path / "sample.csv"
    analysis = hrp.HeartRateAnalysis(df, source_path=source_csv)
    analysis.run_roi(1, cfg={"do_segments": False})
    return analysis


def test_load_results_ignores_unknown_keys(tmp_path, monkeypatch):
    analysis = _make_analysis(tmp_path, monkeypatch)
    json_path = analysis.save_results_json()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    payload["unknown_top_level"] = {"future": True}
    payload["per_roi"]["1"]["cfg"]["future_cfg_knob"] = 123
    payload["per_roi"]["1"]["results"]["lomb"]["unknown_metric"] = 999
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    loaded = hrp.HeartRateAnalysis(analysis.df, source_path=analysis.source_path)
    loaded.load_results_json(json_path)
    out = loaded.get_roi_results(1)
    assert out.lomb is not None and out.lomb.bpm == 420.0


def test_load_results_applies_defaults_for_missing_fields(tmp_path, monkeypatch):
    analysis = _make_analysis(tmp_path, monkeypatch)
    json_path = analysis.save_results_json()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    payload["per_roi"]["1"]["results"]["lomb"].pop("status_note", None)
    payload["per_roi"]["1"]["results"]["welch"].pop("status_note", None)
    payload["per_roi"]["1"]["results"]["analysis_cfg"].pop("seg_step_sec", None)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    loaded = hrp.HeartRateAnalysis(analysis.df, source_path=analysis.source_path)
    loaded.load_results_json(json_path)
    out = loaded.get_roi_results(1)
    assert out.lomb is not None and out.lomb.status_note == ""
    assert out.welch is not None and out.welch.status_note == ""
    assert out.analysis_cfg.seg_step_sec == hrp.HRAnalysisConfig().seg_step_sec
