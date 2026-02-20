"""Dataset-level behavior tests."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path

import numpy as np

from kymflow_zarr import ZarrDataset


def test_iter_records_order_by_acquired_handles_missing(tmp_path: Path) -> None:
    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")

    rec_missing = ds.add_image((np.random.rand(1, 8, 8) * 255).astype(np.uint8))
    rec_with_time = ds.add_image((np.random.rand(1, 8, 8) * 255).astype(np.uint8))
    rec_with_time.save_metadata_payload({"version": "2.0", "header": {"acquired_local_epoch_ns": 123}})

    ds.update_manifest()

    ids_missing_last = [r.image_id for r in ds.iter_records(order_by="acquired_local_epoch_ns", missing="last")]
    ids_missing_first = [r.image_id for r in ds.iter_records(order_by="acquired_local_epoch_ns", missing="first")]

    assert ids_missing_last == [rec_with_time.image_id, rec_missing.image_id]
    assert ids_missing_first == [rec_missing.image_id, rec_with_time.image_id]


def test_ingest_image_with_minimal_source(tmp_path: Path) -> None:
    class Src:
        def __init__(self) -> None:
            self.arr = (np.random.rand(8, 8) * 255).astype(np.uint8)

        def getChannelData(self, channel: int = 1) -> np.ndarray:
            assert channel == 1
            return self.arr

    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.ingest_image(Src())

    assert rec.load_array().shape == (8, 8)


def test_ingest_image_surfaces_metadata_accessor_errors(tmp_path: Path) -> None:
    class Src:
        def __init__(self) -> None:
            self.arr = (np.random.rand(8, 8) * 255).astype(np.uint8)

        def getChannelData(self, channel: int = 1) -> np.ndarray:
            assert channel == 1
            return self.arr

        def getHeader(self):
            raise RuntimeError("header read failed")

    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")

    try:
        ds.ingest_image(Src())
        assert False, "Expected RuntimeError from getHeader()"
    except RuntimeError as e:
        assert "header read failed" in str(e)
