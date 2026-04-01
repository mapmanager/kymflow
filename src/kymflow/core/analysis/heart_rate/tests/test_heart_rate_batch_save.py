from pathlib import Path

import numpy as np
import pandas as pd

import kymflow.core.analysis.heart_rate.heart_rate_pipeline as hrp
from kymflow.core.analysis.heart_rate.heart_rate_analysis import HeartRateEstimate
from kymflow.core.analysis.heart_rate.heart_rate_batch import batch_run_and_save


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


def _write_two_roi_csv(tmp_path: Path, name: str = "sample.csv") -> Path:
    t = np.linspace(0.0, 4.0, 300)
    v1 = np.sin(2.0 * np.pi * 7.0 * t)
    v2 = np.sin(2.0 * np.pi * 7.2 * t)
    df = pd.DataFrame(
        {
            "time": np.concatenate([t, t]),
            "velocity": np.concatenate([v1, v2]),
            "roi_id": np.concatenate([np.ones_like(t, dtype=int), np.full_like(t, 2, dtype=int)]),
        }
    )
    csv_path = tmp_path / name
    df.to_csv(csv_path, index=False)
    return csv_path


def test_batch_run_and_save_serial_happy_path(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)
    csv_path = _write_two_roi_csv(tmp_path)

    out = batch_run_and_save([csv_path], roi_ids=None, cfg=None, backend="serial")
    assert len(out) == 1
    assert out[0].ok is True
    assert out[0].saved_json_path is not None
    assert out[0].saved_json_path.exists()

    analysis = hrp.HeartRateAnalysis.from_csv(csv_path)
    analysis.load_results_json(out[0].saved_json_path)
    assert set(analysis.results_by_roi.keys()) == {1, 2}


def test_batch_run_and_save_overwrite_false_skips_recompute(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)
    csv_path = _write_two_roi_csv(tmp_path, name="skip.csv")

    first = batch_run_and_save([csv_path], backend="serial", overwrite=True)
    second = batch_run_and_save([csv_path], backend="serial", overwrite=False)

    assert first[0].ok and second[0].ok
    assert first[0].saved_json_path == second[0].saved_json_path
    assert second[0].saved_json_path is not None and second[0].saved_json_path.exists()


def test_batch_run_and_save_invalid_roi_reports_error(tmp_path, monkeypatch):
    monkeypatch.setattr(hrp, "estimate_heart_rate_global", _fake_estimator)
    csv_path = _write_two_roi_csv(tmp_path, name="bad_roi.csv")

    out = batch_run_and_save([csv_path], roi_ids=[999], backend="serial")
    assert len(out) == 1
    assert out[0].ok is False
    assert out[0].saved_json_path is None
    assert "not found" in out[0].error.lower()
