"""Manifest robustness tests for malformed metadata blobs."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path

import numpy as np

from kymflow_zarr import ZarrDataset


def test_manifest_rebuild_tolerates_malformed_metadata_payload(tmp_path: Path) -> None:
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))

    bad_key = f"images/{rec.image_id}/analysis/metadata.json"
    ds.store[bad_key] = b"{not valid json"

    m = ds.update_manifest()
    out = [x for x in m.images if x["image_id"] == rec.image_id][0]
    assert out["acquired_local_epoch_ns"] is None
