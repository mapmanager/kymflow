"""Record-level behavior tests."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kymflow_zarr import MetadataNotFoundError, ZarrDataset


def test_missing_metadata_payload_raises_clear_error(tmp_path: Path) -> None:
    ds_path = tmp_path / "ds.zarr"
    ds = ZarrDataset(str(ds_path), mode="a")
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))

    ds_ro = ZarrDataset(str(ds_path), mode="r")
    rec_ro = ds_ro.record(rec.image_id)

    with pytest.raises(MetadataNotFoundError):
        rec_ro.load_metadata_payload()


def test_open_group_missing_record_does_not_create(tmp_path: Path) -> None:
    ds_path = tmp_path / "ds.zarr"
    ds = ZarrDataset(str(ds_path), mode="a")
    _ = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))

    ds_ro = ZarrDataset(str(ds_path), mode="r")
    rec = ds_ro.record("missing-record")

    with pytest.raises(KeyError):
        rec.open_group()

    assert "images/missing-record" not in ds_ro.root
    assert rec.get_axes() is None


def test_delete_analysis_with_suffix_filter(tmp_path: Path) -> None:
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))

    rec.save_json("events", {"n": 2})
    rec.save_json("quality", {"ok": True})
    rec.save_df_csv_gz("roi_table", pd.DataFrame({"roi_id": [1, 2], "peak": [0.2, 0.4]}))

    deleted = rec.delete_analysis(suffixes=(".json.gz",))
    assert deleted == 2

    keys = rec.list_analysis_keys()
    assert len(keys) == 1
    assert keys[0].endswith("roi_table.csv.gz")
