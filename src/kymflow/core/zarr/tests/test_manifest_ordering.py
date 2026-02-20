# Filename: tests/test_manifest_ordering.py
"""Manifest ordering behavior."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path
import numpy as np

from kymflow_zarr import ZarrDataset


def test_iter_records_order_by_created(tmp_path: Path) -> None:
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    for _ in range(3):
        arr = (np.random.rand(1, 8, 8) * 255).astype(np.uint8)
        ds.add_image(arr)
    ds.update_manifest()
    ids = [r.image_id for r in ds.iter_records(order_by="created_utc")]
    assert len(ids) == 3
