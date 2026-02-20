"""Compatibility tests for AcqImageV01 shim methods used by GUI/ROI flows."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

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


def test_acq_image_clean_api_surface() -> None:
    arr = (np.random.rand(10, 20) * 255).astype(np.uint16)
    img = AcqImageV01(
        source_key="img001",
        pixel_store=_FakePixelStore(arr=arr),
        artifact_store=_FakeArtifactStore(payloads={}),
    )

    assert img.channels_available() == [1, 2]
    assert img.get_channel(1).shape == (10, 20)

    b1 = _bounds_dims(img.get_image_bounds())
    assert b1 == (20, 10, 1)

    assert not hasattr(img, "getChannelKeys")
    assert not hasattr(img, "getImageBounds")
    assert not hasattr(img, "get_img_slice")
    assert not hasattr(img, "mark_metadata_dirty")
    assert not hasattr(img, "is_metadata_dirty")

    img.save_metadata_payload({"version": "2.0"})


def test_roi_channel_validation_uses_channels_available() -> None:
    pytest.importorskip("kymflow")
    roi_mod = pytest.importorskip("kymflow.core.image_loaders.roi")
    RoiBounds = roi_mod.RoiBounds

    arr = (np.random.rand(30, 30) * 255).astype(np.uint16)
    img = AcqImageV01(
        source_key="img001",
        pixel_store=_FakePixelStore(arr=arr),
        artifact_store=_FakeArtifactStore(payloads={}),
    )

    rid = img.add_roi(RoiBounds(1, 10, 1, 10), channel=1, z=0, name="ok", note="")
    assert rid > 0

    with pytest.raises(ValueError):
        img.add_roi(RoiBounds(1, 10, 1, 10), channel=99, z=0, name="bad", note="")
