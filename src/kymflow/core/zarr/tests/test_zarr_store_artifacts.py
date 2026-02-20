"""Tests for ZarrStore artifact loading behavior."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path

import numpy as np
import pytest

from kymflow_zarr import ZarrDataset
from kymflow_zarr.experimental_stores.stores.zarr_store import ZarrStore


def test_zarr_store_load_dict_returns_default_for_missing(tmp_path: Path) -> None:
    ds_path = tmp_path / "ds.zarr"
    ds = ZarrDataset(str(ds_path), mode="a")
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))

    store = ZarrStore(str(ds_path))
    out = store.load_dict(rec.image_id, "missing_name", default={"ok": 1})
    assert out == {"ok": 1}


def test_zarr_store_load_dict_does_not_swallow_decode_errors(tmp_path: Path) -> None:
    ds_path = tmp_path / "ds.zarr"
    ds = ZarrDataset(str(ds_path), mode="a")
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))

    key = f"images/{rec.image_id}/analysis/bad.json.gz"
    ds.store[key] = b"this is not gzip data"

    store = ZarrStore(str(ds_path))
    with pytest.raises(OSError):
        _ = store.load_dict(rec.image_id, "bad")
