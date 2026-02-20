"""Metadata/ROI roundtrip tests with kymflow objects when available."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from kymflow_zarr import ZarrDataset
from kymflow_zarr.experimental_stores.acq_image import AcqImageV01
from kymflow_zarr.experimental_stores.stores.base import ImageInfo


@dataclass
class _FakePixelStore:
    arr: np.ndarray

    def describe(self, key: str) -> ImageInfo:
        return ImageInfo(shape=tuple(self.arr.shape), ndim=int(self.arr.ndim), dtype=str(self.arr.dtype), axes=("y", "x"))

    def load_channel(self, key: str, channel: int) -> np.ndarray:
        if channel != 1:
            raise ValueError("missing channel")
        return self.arr

    def discover_channel_paths(self, key: str) -> dict[int, str] | None:
        return {1: f"{key}_c1.tif"}


@dataclass
class _FakeArtifactStore:
    payloads: dict[tuple[str, str], dict[str, Any]]

    def load_dict(self, key: str, name: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return dict(self.payloads.get((key, name), {} if default is None else default))

    def save_dict(self, key: str, name: str, dct: dict[str, Any]) -> None:
        self.payloads[(key, name)] = dict(dct)


def test_metadata_and_roi_roundtrip_through_ingest(tmp_path: Path) -> None:
    pytest.importorskip("kymflow")
    roi_mod = pytest.importorskip("kymflow.core.image_loaders.roi")
    RoiBounds = roi_mod.RoiBounds

    arr = (np.random.rand(100, 30) * 255).astype(np.uint16)
    src = AcqImageV01(
        key="img001",
        pixel_store=_FakePixelStore(arr=arr),
        artifact_store=_FakeArtifactStore(payloads={}),
    )

    src.add_roi(RoiBounds(10, 30, 2, 12), channel=1, z=0, name="roi1", note="")
    src.save_metadata_objects(auto_header_from_pixels=True)

    ds = ZarrDataset(str(tmp_path / "ds.zarr"), mode="a")
    rec = ds.ingest_image(src)

    payload = rec.load_metadata_payload()
    assert "header" in payload
    assert isinstance(payload.get("rois"), list)
    assert len(payload.get("rois", [])) == 1

    hdr, _em, rois = rec.load_metadata_objects()
    assert hdr is not None
    assert rois.numRois() == 1


def test_malformed_rois_payload_raises_in_acqimage() -> None:
    pytest.importorskip("kymflow")

    arr = (np.random.rand(20, 20) * 255).astype(np.uint16)
    src = AcqImageV01(
        key="img001",
        pixel_store=_FakePixelStore(arr=arr),
        artifact_store=_FakeArtifactStore(payloads={("img001", "metadata"): {"version": "2.0", "rois": {"bad": 1}}}),
    )

    with pytest.raises(TypeError):
        _ = src.rois()
