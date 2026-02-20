"""Tests for KymDataset orchestrator and dataset indexers."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kymflow.core.zarr.indexers.radon_report import RadonReportIndexer
from kymflow.core.zarr.indexers.velocity_events import VelocityEventsIndexer
from kymflow.core.zarr.kym_dataset import KymDataset
from kymflow_zarr import ZarrDataset


def _mk_record(ds: ZarrDataset) -> str:
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))
    return rec.image_id


def test_kym_dataset_rebuild_and_update_image(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")

    id1 = _mk_record(ds)
    id2 = _mk_record(ds)
    id3 = _mk_record(ds)

    rec1 = ds.record(id1)
    rec2 = ds.record(id2)
    rec3 = ds.record(id3)

    rec1.save_df_parquet(
        "velocity_events",
        pd.DataFrame(
            {
                "roi_id": [1, 2],
                "event_id": ["e1", "e2"],
                "t0_s": [0.1, 0.2],
                "t1_s": [0.3, 0.4],
                "kind": ["drop", "drop"],
                "score": [0.8, 0.6],
            }
        ),
    )
    rec2.save_df_parquet(
        "velocity_events",
        pd.DataFrame(
            {
                "roi_id": [3],
                "event_id": ["e3"],
                "t0_s": [0.5],
                "t1_s": [0.7],
                "kind": ["rise"],
                "score": [0.9],
            }
        ),
    )

    rec1.save_json("radon_report", {"mean_velocity": 0.2, "median_velocity": 0.18, "n_valid": 100, "notes": "ok"})
    rec2.save_df_parquet(
        "radon_report",
        pd.DataFrame({"mean_velocity": [0.4], "median_velocity": [0.35], "n_valid": [80], "notes": ["good"]}),
    )
    rec3.save_json("radon_report", {"mean_velocity": 0.1, "median_velocity": 0.09, "n_valid": 20, "notes": "sparse"})

    kds = KymDataset(str(tmp_path / "ds.zarr"), mode="a")
    ve_idx = VelocityEventsIndexer()
    rr_idx = RadonReportIndexer()

    ve = kds.rebuild(ve_idx)
    assert len(ve) == 3
    assert "image_id" in ve.columns
    assert set(ve["image_id"]) == {id1, id2}

    rr = kds.rebuild(rr_idx)
    assert len(rr) == 3
    assert set(rr["image_id"]) == {id1, id2, id3}

    rec2.save_df_parquet(
        "velocity_events",
        pd.DataFrame(
            {
                "roi_id": [9],
                "event_id": ["e9"],
                "t0_s": [1.0],
                "t1_s": [1.2],
                "kind": ["drop"],
                "score": [0.4],
            }
        ),
    )
    updated = kds.update_image(ve_idx, id2)
    rows_id2 = updated[updated["image_id"] == id2]
    assert len(rows_id2) == 1
    assert rows_id2.iloc[0]["event_id"] == "e9"

    loaded = kds.get_table("velocity_events")
    assert len(loaded) == len(updated)
