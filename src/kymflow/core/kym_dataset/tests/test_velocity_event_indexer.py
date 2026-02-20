"""Integration tests for VelocityEventIndexer + incremental KymDataset updates."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kymflow.core.kym_dataset.indexers.velocity_events import VelocityEventIndexer
from kymflow.core.kym_dataset.kym_dataset import KymDataset
from kymflow.core.kym_dataset.provenance import params_hash as compute_params_hash
from kymflow.core.kym_dataset.staleness import StalenessReason
from kymflow_zarr import ZarrDataset


def _mk_record(ds: ZarrDataset, *, threshold: float, score: float) -> str:
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))
    rec.save_json("velocity_events/params", {"threshold": threshold, "window": 5})
    rec.save_df_parquet(
        "velocity_events/events",
        pd.DataFrame(
            {
                "roi_id": [1],
                "event_id": [f"ev-{rec.image_id[:6]}"],
                "t_start_s": [0.1],
                "t_end_s": [0.2],
                "peak_t_s": [0.15],
                "peak_value": [1.1],
                "score": [score],
            }
        ),
    )
    return rec.image_id


def test_velocity_event_indexer_replace_and_incremental(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    id1 = _mk_record(ds, threshold=0.20, score=0.9)
    id2 = _mk_record(ds, threshold=0.30, score=0.8)

    kd = KymDataset(ds)
    idx = VelocityEventIndexer()

    kd.update_index(idx, mode="replace")
    out = ds.load_table("kym_velocity_events")
    assert len(out) == 2
    assert "tables/kym_velocity_events.parquet" in ds.store
    assert set(out["image_id"]) == {id1, id2}

    kd.update_index(idx, mode="incremental")
    assert kd.last_update_stats["updated"] == 0
    assert kd.last_update_stats["skipped_fresh"] == 2
    assert kd.last_update_stats["skipped_zero_rows"] == 0
    assert kd.last_update_stats["stale_missing_marker"] == 0
    assert kd.last_update_stats["stale_marker_table_mismatch"] == 0

    # Change params for one image only -> one update expected.
    rec1 = ds.record(id1)
    rec1.save_json("velocity_events/params", {"threshold": 0.75, "window": 5})
    kd.update_index(idx, mode="incremental")
    assert kd.last_update_stats["updated"] == 1
    assert kd.last_update_stats["skipped_fresh"] == 1
    assert kd.last_update_stats["skipped_zero_rows"] == 0
    assert kd.last_update_stats["stale_missing_marker"] == 0
    assert kd.last_update_stats["stale_marker_table_mismatch"] == 0

    out2 = ds.load_table("kym_velocity_events")
    h1 = out2[out2["image_id"] == id1]["params_hash"].iloc[0]
    h2 = out2[out2["image_id"] == id2]["params_hash"].iloc[0]
    assert h1 != h2


def test_velocity_events_zero_rows_uses_run_marker_for_incremental_skip(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))

    params = {"threshold": 0.2, "window": 5}
    rec.save_json("velocity_events/params", params)
    rec.save_df_parquet(
        "velocity_events/events",
        pd.DataFrame(columns=["roi_id", "event_id", "t_start_s", "t_end_s", "peak_t_s", "peak_value", "score"]),
    )

    idx = VelocityEventIndexer()
    p_hash = compute_params_hash(params)
    idx.write_run_marker(
        rec,
        params_hash=p_hash,
        analysis_version=idx.analysis_version(),
        n_rows=0,
    )

    kd = KymDataset(ds)
    kd.update_index(idx, mode="replace")
    out = ds.load_table("kym_velocity_events")
    assert len(out) == 0
    assert kd.last_update_stats["updated"] == 1

    kd.update_index(idx, mode="incremental")
    assert kd.last_update_stats["updated"] == 0
    assert kd.last_update_stats["skipped_fresh"] == 0
    assert kd.last_update_stats["skipped_zero_rows"] == 1
    assert kd.last_update_stats["stale_missing_marker"] == 0
    assert kd.last_update_stats["stale_marker_table_mismatch"] == 0

    stale = kd.get_staleness(
        "kym_velocity_events",
        rec.image_id,
        idx.params_hash(rec),
        analysis_version=idx.analysis_version(),
        indexer=idx,
        rec=rec,
    )
    assert stale.has_run_marker is True
    assert stale.table_rows_present is False
    assert stale.is_stale is False
    assert stale.reason == StalenessReason.FRESH_ZERO_ROWS

    rec.save_json("velocity_events/params", {"threshold": 0.9, "window": 5})
    kd.update_index(idx, mode="incremental")
    assert kd.last_update_stats["updated"] == 1
    assert kd.last_update_stats["skipped_fresh"] == 0
    assert kd.last_update_stats["skipped_zero_rows"] == 0


def test_zero_rows_rerun_removes_prior_rows(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = _mk_record(ds, threshold=0.20, score=0.9)
    kd = KymDataset(ds)
    idx = VelocityEventIndexer()

    kd.update_index(idx, mode="replace")
    assert len(ds.load_table("kym_velocity_events")) == 1

    rec_obj = ds.record(rec)
    rec_obj.save_df_parquet(
        "velocity_events/events",
        pd.DataFrame(columns=["roi_id", "event_id", "t_start_s", "t_end_s", "peak_t_s", "peak_value", "score"]),
    )
    params = {"threshold": 0.20, "window": 5}
    idx.write_run_marker(
        rec_obj,
        params_hash=compute_params_hash(params),
        analysis_version=idx.analysis_version(),
        n_rows=0,
    )

    kd.update_index(idx, mode="incremental")
    out = ds.load_table("kym_velocity_events")
    assert len(out) == 0
    assert kd.last_update_stats["updated"] == 1


def test_staleness_missing_marker_and_marker_table_mismatch(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))
    rec.save_json("velocity_events/params", {"threshold": 0.2, "window": 5})
    idx = VelocityEventIndexer()
    kd = KymDataset(ds)

    stale = kd.get_staleness(
        "kym_velocity_events",
        rec.image_id,
        idx.params_hash(rec),
        analysis_version=idx.analysis_version(),
        indexer=idx,
        rec=rec,
    )
    assert stale.is_stale is True
    assert stale.reason == StalenessReason.STALE_MISSING_MARKER
    kd.update_index(idx, mode="incremental")
    assert kd.last_update_stats["updated"] == 1
    assert kd.last_update_stats["stale_missing_marker"] == 1

    # Create table rows, then force marker to claim zero rows for same params.
    rec.save_df_parquet(
        "velocity_events/events",
        pd.DataFrame(
            {
                "roi_id": [1],
                "event_id": ["e1"],
                "t_start_s": [0.1],
                "t_end_s": [0.2],
                "peak_t_s": [0.15],
                "peak_value": [1.0],
                "score": [0.9],
            }
        ),
    )
    kd.update_index(idx, mode="replace")
    marker_hash = idx.params_hash(rec)
    idx.write_run_marker(
        rec,
        params_hash=marker_hash,
        analysis_version=idx.analysis_version(),
        n_rows=0,
    )
    mismatch = kd.get_staleness(
        "kym_velocity_events",
        rec.image_id,
        marker_hash,
        analysis_version=idx.analysis_version(),
        indexer=idx,
        rec=rec,
    )
    assert mismatch.is_stale is True
    assert mismatch.reason == StalenessReason.STALE_MARKER_TABLE_MISMATCH

    # Source-of-truth now empty, so rebuild should be triggered by mismatch and clear rows.
    rec.save_df_parquet(
        "velocity_events/events",
        pd.DataFrame(columns=["roi_id", "event_id", "t_start_s", "t_end_s", "peak_t_s", "peak_value", "score"]),
    )

    kd.update_index(idx, mode="incremental")
    assert kd.last_update_stats["updated"] == 1
    assert kd.last_update_stats["stale_marker_table_mismatch"] == 1
    out = ds.load_table("kym_velocity_events")
    assert len(out) == 0

    stale2 = kd.get_staleness(
        "kym_velocity_events",
        rec.image_id,
        marker_hash,
        analysis_version=idx.analysis_version(),
        indexer=idx,
        rec=rec,
    )
    assert stale2.reason == StalenessReason.FRESH_ZERO_ROWS
