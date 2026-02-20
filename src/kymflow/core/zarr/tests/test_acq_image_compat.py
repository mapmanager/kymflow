"""Compatibility tests for AcqImageV01 shim methods used by GUI/ROI flows."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass
from typing import Any

import numpy as np

from kymflow_zarr.experimental_stores.acq_image import AcqImageV01
from kymflow_zarr.experimental_stores.stores.base import ImageInfo


@dataclass
class _FakePixelStore:
    arr: np.ndarray

    def describe(self, key: str) -> ImageInfo:
        return ImageInfo(shape=tuple(self.arr.shape), ndim=int(self.arr.ndim), dtype=str(self.arr.dtype), axes=("y", "x"))

    def load_channel(self, key: str, channel: int) -> np.ndarray:
        if channel == 1:
            return self.arr
        if channel == 2:
            return self.arr + 1
        raise ValueError("missing channel")

    def discover_channel_paths(self, key: str) -> dict[int, str] | None:
        return {1: f"{key}_c1.tif", 2: f"{key}_c2.tif"}


@dataclass
class _FakeArtifactStore:
    payloads: dict[tuple[str, str], dict[str, Any]]

    def load_dict(self, key: str, name: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return dict(self.payloads.get((key, name), {} if default is None else default))

    def save_dict(self, key: str, name: str, dct: dict[str, Any]) -> None:
        self.payloads[(key, name)] = dict(dct)


def _bounds_dims(bounds: Any) -> tuple[int, int, int]:
    if isinstance(bounds, dict):
        return int(bounds["width"]), int(bounds["height"]), int(bounds["num_slices"])
    return int(getattr(bounds, "width")), int(getattr(bounds, "height")), int(getattr(bounds, "num_slices"))


def test_acq_image_compat_shims_and_dirty_tracking() -> None:
    arr = (np.random.rand(10, 20) * 255).astype(np.uint16)
    img = AcqImageV01(
        key="img001",
        pixel_store=_FakePixelStore(arr=arr),
        artifact_store=_FakeArtifactStore(payloads={}),
    )

    assert img.channels_available() == [1, 2]
    assert img.getChannelKeys() == [1, 2]

    b1 = _bounds_dims(img.get_image_bounds())
    b2 = _bounds_dims(img.getImageBounds())
    assert b1 == b2 == (20, 10, 1)

    assert img.get_img_slice(slice_num=0, channel=1).shape == (10, 20)
    assert img.get_img_slice(slice_num=0, channel=999) is None

    assert img.is_metadata_dirty is False
    img.mark_metadata_dirty()
    assert img.is_metadata_dirty is True
    img.save_metadata_payload({"version": "2.0"})
    assert img.is_metadata_dirty is False
