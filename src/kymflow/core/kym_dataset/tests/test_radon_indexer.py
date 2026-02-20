"""Integration tests for ROI-driven RadonIndexer staleness behavior."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kymflow.core.kym_dataset.indexers.radon import RadonIndexer
from kymflow.core.kym_dataset.kym_dataset import KymDataset
from kymflow_zarr import ZarrDataset


def test_radon_indexer_incremental_recompute_on_roi_edit(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))

    rec.save_json("radon/params", {"window": 11, "step": 2})
    rec.save_metadata_payload(
        {
            "version": "2.0",
            "rois": [
                {
                    "roi_id": 1,
                    "roi_type": "rect",
                    "version": "1.0",
                    "name": "r1",
                    "note": "",
                    "channel": 1,
                    "z": 0,
                    "data": {"x0": 1, "x1": 6, "y0": 2, "y1": 7},
                    "meta": {},
                }
            ],
        }
    )
    rec.save_df_parquet("radon/results", pd.DataFrame({"roi_id": [1], "velocity": [0.42]}))

    idx = RadonIndexer()
    kd = KymDataset(ds)

    kd.update_index(idx, mode="replace")
    out = ds.load_table("kym_radon")
    assert len(out) == 1

    kd.update_index(idx, mode="incremental")
    assert kd.last_update_stats["updated"] == 0
    assert kd.last_update_stats["skipped"] == 1

    md = rec.load_metadata_payload()
    roi0 = md["rois"][0]
    roi0["data"]["x1"] = 7  # geometry edit -> hash must change
    rec.save_metadata_payload(md)

    kd.update_index(idx, mode="incremental")
    assert kd.last_update_stats["updated"] == 1
    assert kd.last_update_stats["skipped"] == 0
