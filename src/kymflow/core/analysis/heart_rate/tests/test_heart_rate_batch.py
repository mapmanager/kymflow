from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import kymflow.core.analysis.heart_rate.heart_rate_pipeline as hrp
from kymflow.core.analysis.heart_rate.heart_rate_analysis import HeartRateEstimate
from kymflow.core.analysis.heart_rate.heart_rate_batch import (
    HRBatchTask,
    batch_results_to_dataframe,
    run_hr_batch,
)


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


def _make_df() -> pd.DataFrame:
    t = np.linspace(0.0, 4.0, 401)
    v = np.sin(2.0 * np.pi * 7.0 * t)
    return pd.DataFrame({"time": t, "velocity": v, "roi_id": np.ones_like(t, dtype=int)})


def test_df_init_requires_roi_column():
    df = pd.DataFrame({"time": [0.0, 0.01], "velocity": [1.0, 1.1]})
    with pytest.raises(ValueError, match="roi_id"):
        hrp.HeartRateAnalysis(df)


def test_results_json_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)
    df = _make_df()
    source_csv = tmp_path / "sample.csv"

    analysis = hrp.HeartRateAnalysis(df, source_path=source_csv)
    analysis.run_roi(1, cfg={"do_segments": False})
    out_path = analysis.save_results_json()

    assert out_path == tmp_path / "sample_heart_rate.json"
    assert out_path.exists()

    loaded = hrp.HeartRateAnalysis(df, source_path=source_csv)
    loaded.load_results_json(out_path)
    r = loaded.get_roi_results(1)
    assert r.lomb is not None and r.lomb.bpm == 420.0
    assert r.welch is not None and r.welch.bpm == 426.0


def test_batch_thread_backend_supports_df_tasks(monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)
    df = _make_df()
    task = HRBatchTask(df=df, source_id="in_memory_df")
    out = run_hr_batch([task], backend="thread", n_workers=1)

    assert len(out) == 1
    assert out[0].source_id == "in_memory_df"
    assert 1 in out[0].per_roi

    mini_df = batch_results_to_dataframe(out, minimal="mini")
    assert mini_df.shape[0] == 1
    assert mini_df.loc[0, "file"] == "in_memory_df"
    assert mini_df.loc[0, "roi_id"] == 1


def test_batch_process_backend_rejects_df_tasks():
    df = _make_df()
    task = HRBatchTask(df=df, source_id="in_memory_df")
    with pytest.raises(ValueError, match="csv_path only"):
        run_hr_batch([task], backend="process")
