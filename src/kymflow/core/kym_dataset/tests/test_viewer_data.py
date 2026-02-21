"""Smoke tests for viewer dataframe helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kymflow.core.kym_dataset.viewer_data import build_viewer_dataframe
from kymflow.core.kym_dataset.viewer_table import build_dataset_view_table
from kymflow_zarr import ZarrDataset


def test_build_viewer_dataframe_smoke(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.add_image((np.random.rand(6, 7) * 255).astype(np.uint8))
    rec.save_json(
        "provenance",
        {"original_path": "/tmp/a.tif", "file_size": 42, "mtime_ns": 123},
    )
    rec.save_metadata_payload({"version": "2.0", "header": {"acquired_local_epoch_ns": 99}})
    ds.save_table("kym_velocity_events", pd.DataFrame({"image_id": [rec.image_id], "score": [0.5]}))

    df = build_viewer_dataframe(ds)
    assert len(df) == 1
    assert "image_id" in df.columns
    assert "original_path" in df.columns
    assert "acquired_local_epoch_ns" in df.columns
    assert "velocity_event_count" in df.columns


def test_build_viewer_dataframe_is_wrapper(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    ds = ZarrDataset(str(tmp_path / "ds2.zarr"), mode="a")
    rec = ds.add_image((np.random.rand(4, 5) * 255).astype(np.uint8))
    ds.save_table("kym_velocity_events", pd.DataFrame({"image_id": [rec.image_id]}))

    wrapper = build_viewer_dataframe(ds)
    direct = build_dataset_view_table(ds, include_tables=["kym_velocity_events"]).copy()
    if "n_rows_kym_velocity_events" in direct.columns:
        direct["velocity_event_count"] = direct["n_rows_kym_velocity_events"]

    assert list(wrapper.columns) == list(direct.columns)
    pd.testing.assert_frame_equal(wrapper.reset_index(drop=True), direct.reset_index(drop=True))
