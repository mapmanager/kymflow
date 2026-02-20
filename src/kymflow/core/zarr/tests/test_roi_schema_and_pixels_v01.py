"""ROI envelope + ROI pixels/mask/stats tests for AcqImageV01."""

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
    axes: tuple[str, ...]

    def describe(self, key: str) -> ImageInfo:
        return ImageInfo(shape=tuple(self.arr.shape), ndim=int(self.arr.ndim), dtype=str(self.arr.dtype), axes=self.axes)

    def load_channel(self, key: str, channel: int) -> np.ndarray:
        if "c" in self.axes:
            c_axis = self.axes.index("c")
            c_dim = self.arr.shape[c_axis]
            c_idx = channel - 1
            if c_idx < 0 or c_idx >= c_dim:
                raise ValueError(f"missing channel {channel}")
            sl = [slice(None)] * self.arr.ndim
            sl[c_axis] = c_idx
            return np.asarray(self.arr[tuple(sl)])
        if channel != 1:
            raise ValueError(f"missing channel {channel}")
        return np.asarray(self.arr)

    def discover_channel_paths(self, key: str) -> dict[int, str] | None:
        if "c" not in self.axes:
            return {1: f"{key}_c1"}
        n_channels = int(self.arr.shape[self.axes.index("c")])
        return {idx + 1: f"{key}_c{idx + 1}" for idx in range(n_channels)}


@dataclass
class _FakeArtifactStore:
    payloads: dict[tuple[str, str], dict[str, Any]]
    arrays: dict[tuple[str, str], np.ndarray] | None = None

    def load_dict(self, key: str, name: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return dict(self.payloads.get((key, name), {} if default is None else default))

    def save_dict(self, key: str, name: str, dct: dict[str, Any]) -> None:
        self.payloads[(key, name)] = dict(dct)

    def save_array_artifact(
        self,
        key: str,
        name: str,
        arr: np.ndarray,
        *,
        axes: list[str] | None = None,
        chunks: tuple[int, ...] | None = None,
    ) -> None:
        if self.arrays is None:
            self.arrays = {}
        self.arrays[(key, name)] = np.asarray(arr).copy()

    def load_array_artifact(self, key: str, name: str) -> np.ndarray:
        if self.arrays is None or (key, name) not in self.arrays:
            raise FileNotFoundError(name)
        return np.asarray(self.arrays[(key, name)])

    def list_array_artifacts(self, key: str) -> list[str]:
        if self.arrays is None:
            return []
        return sorted(name for k, name in self.arrays.keys() if k == key)


def test_roi_envelope_roundtrip_and_legacy_upgrade() -> None:
    pytest.importorskip("kymflow")
    roi_mod = pytest.importorskip("kymflow.core.image_loaders.roi")
    RoiBounds = roi_mod.RoiBounds
    RoiSet = roi_mod.RoiSet
    RectROI = roi_mod.RectROI
    roi_from_dict = roi_mod.roi_from_dict

    arr = np.arange(10 * 12, dtype=np.uint16).reshape(10, 12)
    img = AcqImageV01(
        source_key="img001",
        pixel_store=_FakePixelStore(arr=arr, axes=("y", "x")),
        artifact_store=_FakeArtifactStore(payloads={}),
    )

    rid = img.add_roi(RoiBounds(2, 6, 3, 8), channel=1, z=0, name="roi1", note="")
    assert rid > 0
    img.save_metadata_objects(auto_header_from_pixels=True)

    payload = img.load_metadata_payload()
    roi_payload = payload["rois"][0]
    assert roi_payload["roi_type"] == "rect"
    assert roi_payload["version"] == "1.0"
    assert isinstance(roi_payload["data"], dict)
    assert roi_payload["data"]["x0"] == 3
    assert roi_payload["data"]["x1"] == 8
    assert roi_payload["data"]["y0"] == 2
    assert roi_payload["data"]["y1"] == 6
    assert isinstance(roi_payload["meta"], dict)

    legacy = {"id": 42, "channel": 1, "z": 0, "name": "legacy", "note": "", "dim0_start": 1, "dim0_stop": 4, "dim1_start": 2, "dim1_stop": 6}
    roi_obj = roi_from_dict(legacy)
    assert isinstance(roi_obj, RectROI)
    upgraded = roi_obj.to_dict()
    assert upgraded["roi_type"] == "rect"
    assert upgraded["roi_id"] == 42
    assert upgraded["data"] == {"x0": 2, "x1": 6, "y0": 1, "y1": 4}

    rs = RoiSet.from_list([legacy], img)
    out = rs.to_list()[0]
    assert out["roi_type"] == "rect"
    assert out["roi_id"] == 42


def test_roi_factory_errors_are_actionable() -> None:
    pytest.importorskip("kymflow")
    roi_mod = pytest.importorskip("kymflow.core.image_loaders.roi")
    roi_from_dict = roi_mod.roi_from_dict
    MaskROI = roi_mod.MaskROI

    with pytest.raises(ValueError, match="Unknown roi_type"):
        roi_from_dict({"roi_type": "banana", "roi_id": 1, "data": {}})

    mask_obj = roi_from_dict({"roi_type": "mask", "roi_id": 7, "data": {"mask_ref": "analysis_arrays/rois/masks/7"}})
    assert isinstance(mask_obj, MaskROI)
    assert mask_obj.mask_ref == "analysis_arrays/rois/masks/7"


def test_get_roi_pixels_mask_and_stats_4d() -> None:
    pytest.importorskip("kymflow")
    roi_mod = pytest.importorskip("kymflow.core.image_loaders.roi")
    RoiBounds = roi_mod.RoiBounds

    arr = np.arange(2 * 10 * 12 * 3, dtype=np.int32).reshape(2, 10, 12, 3)
    img = AcqImageV01(
        source_key="img001",
        pixel_store=_FakePixelStore(arr=arr, axes=("z", "y", "x", "c")),
        artifact_store=_FakeArtifactStore(payloads={}),
    )

    rid = img.add_roi(RoiBounds(2, 6, 3, 8), channel=2, z=1, name="roi1", note="")
    pix = img.get_roi_pixels(rid)
    exp = arr[1, 2:6, 3:8, 1]
    assert pix.shape == exp.shape
    assert np.array_equal(pix, exp)

    mask = img.get_roi_mask(rid)
    assert mask.shape == pix.shape
    assert mask.dtype == np.bool_
    assert bool(np.all(mask))

    stats = img.roi_stats(rid)
    assert stats["n"] == float(exp.size)
    assert stats["min"] == float(np.min(exp))
    assert stats["max"] == float(np.max(exp))
    assert np.isclose(stats["mean"], float(np.mean(exp)))
    assert np.isclose(stats["std"], float(np.std(exp)))


def test_get_roi_pixels_uses_t0_for_5d() -> None:
    pytest.importorskip("kymflow")
    roi_mod = pytest.importorskip("kymflow.core.image_loaders.roi")
    RoiBounds = roi_mod.RoiBounds

    arr = np.arange(2 * 2 * 6 * 7 * 2, dtype=np.int32).reshape(2, 2, 6, 7, 2)
    img = AcqImageV01(
        source_key="img001",
        pixel_store=_FakePixelStore(arr=arr, axes=("t", "z", "y", "x", "c")),
        artifact_store=_FakeArtifactStore(payloads={}),
    )

    rid = img.add_roi(RoiBounds(1, 5, 2, 6), channel=2, z=1, name="roi_tzyxc", note="")
    pix = img.get_roi_pixels(rid)
    exp = arr[0, 1, 1:5, 2:6, 1]
    assert np.array_equal(pix, exp)


def test_materialize_rect_roi_mask_updates_metadata_and_artifact() -> None:
    pytest.importorskip("kymflow")
    roi_mod = pytest.importorskip("kymflow.core.image_loaders.roi")
    RoiBounds = roi_mod.RoiBounds

    arr = np.arange(9 * 10, dtype=np.uint16).reshape(9, 10)
    art_store = _FakeArtifactStore(payloads={}, arrays={})
    img = AcqImageV01(
        source_key="img001",
        pixel_store=_FakePixelStore(arr=arr, axes=("y", "x")),
        artifact_store=art_store,
    )

    rid = img.add_roi(RoiBounds(2, 7, 3, 9), channel=1, z=0, name="roi1", note="")
    img.save_metadata_objects(auto_header_from_pixels=True)
    ref = img.materialize_rect_roi_mask(rid)

    assert ref == f"analysis_arrays/roi_mask_{rid}"
    saved = art_store.load_array_artifact("img001", f"roi_mask_{rid}")
    assert saved.dtype == np.bool_
    assert saved.shape == (5, 6)
    assert bool(np.all(saved))

    payload = img.load_metadata_payload()
    roi_payload = payload["rois"][0]
    assert roi_payload["meta"]["mask_ref"] == ref
