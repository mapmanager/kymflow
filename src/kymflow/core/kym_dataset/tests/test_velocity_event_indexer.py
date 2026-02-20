"""Integration tests for VelocityEventIndexer + incremental KymDataset updates."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kymflow.core.kym_dataset.indexers.velocity_events import VelocityEventIndexer
from kymflow.core.kym_dataset.kym_dataset import KymDataset
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
    assert kd.last_update_stats["skipped"] == 2
    assert kd.last_update_stats["missing"] == 0

    # Change params for one image only -> one update expected.
    rec1 = ds.record(id1)
    rec1.save_json("velocity_events/params", {"threshold": 0.75, "window": 5})
    kd.update_index(idx, mode="incremental")
    assert kd.last_update_stats["updated"] == 1
    assert kd.last_update_stats["skipped"] == 1
    assert kd.last_update_stats["missing"] == 0

    out2 = ds.load_table("kym_velocity_events")
    h1 = out2[out2["image_id"] == id1]["params_hash"].iloc[0]
    h2 = out2[out2["image_id"] == id2]["params_hash"].iloc[0]
    assert h1 != h2
