# Filename: src/kymflow_zarr/experimental_stores/stores/zarr_store.py
"""Zarr-backed stores wrapping ZarrDataset/Record."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass
import numpy as np

from kymflow_zarr import MetadataNotFoundError, ZarrDataset
from .base import ImageInfo


@dataclass
class ZarrStore:
    """Combined PixelStore+ArtifactStore for a Zarr dataset."""

    dataset_path: str

    def __post_init__(self) -> None:
        self.ds = ZarrDataset(self.dataset_path, mode="a")

    def describe(self, key: str) -> ImageInfo:
        rec = self.ds.record(key)
        arr = rec.open_array()
        axes = rec.get_axes()
        return ImageInfo(shape=tuple(arr.shape), ndim=int(arr.ndim), dtype=str(arr.dtype), axes=axes)

    def load_channel(self, key: str, channel: int) -> np.ndarray:
        rec = self.ds.record(key)
        arr = rec.open_array()
        axes = rec.get_axes()
        if axes and "c" in axes:
            c_axis = axes.index("c")
            idx = channel - 1
            sl = [slice(None)] * arr.ndim
            sl[c_axis] = idx
            return arr[tuple(sl)]
        if channel != 1:
            raise ValueError("No channel axis; use channel=1")
        return arr[:]

    # ArtifactStore (dict-only for v0.1)
    def load_dict(self, key: str, name: str, *, default=None):
        rec = self.ds.record(key)
        try:
            return rec.load_json(name)
        except (KeyError, MetadataNotFoundError):
            return {} if default is None else default

    def save_dict(self, key: str, name: str, dct):
        rec = self.ds.record(key)
        rec.save_json(name, dct)
