"""Tests for dataset-level viewer table helper."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kymflow.core.kym_dataset.viewer_table import build_dataset_view_table
from kymflow_zarr import ZarrDataset


def test_build_dataset_view_table_with_table_counts(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec1 = ds.add_image((np.random.rand(6, 7) * 255).astype(np.uint8))
    rec2 = ds.add_image((np.random.rand(6, 7) * 255).astype(np.uint8))

    rec1.save_metadata_payload({"version": "2.0", "header": {"acquired_local_epoch_ns": 200}})
    rec2.save_metadata_payload({"version": "2.0", "header": {"acquired_local_epoch_ns": 100}})

    ds.save_table(
        "kym_velocity_events",
        pd.DataFrame(
            {
                "image_id": [rec1.image_id, rec1.image_id, rec2.image_id],
                "score": [0.1, 0.2, 0.3],
            }
        ),
    )

    out = build_dataset_view_table(ds, include_tables=["kym_velocity_events"])
    assert len(out) == 2
    assert "n_rows_kym_velocity_events" in out.columns
    counts = {str(r["image_id"]): int(r["n_rows_kym_velocity_events"]) for _, r in out.iterrows()}
    assert counts[rec1.image_id] == 2
    assert counts[rec2.image_id] == 1

    # iter_records(order_by="acquired_local_epoch_ns") uses acquired ordering when present.
    assert out.iloc[0]["image_id"] == rec2.image_id
