# Filename: src/kymflow_zarr/experimental_stores/acq_image.py
"""Experimental AcqImageV01 (store-backed).

Goals for v0.1:
  - Provide an AcqImage-like API that is backend-agnostic (TIFF+sidecar or Zarr).
  - Support ROI CRUD operations in-memory and serialize via the canonical 'metadata' dict artifact.
  - Keep GUI code thin: GUI should call AcqImage methods, not ZarrDataset/Record internals.

Notes:
  - ROI/metadata object conveniences require the main `kymflow` package to be importable.
  - When `kymflow` is not available, metadata is still accessible as a raw dict payload.
"""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .stores import ArtifactStore, PixelStore, stores_for_path


def _require_kymflow() -> None:
    try:
        import kymflow  # noqa: F401
    except ImportError as e:  # pragma: no cover
        raise ImportError("kymflow must be installed to use ROI/metadata object APIs") from e


@dataclass
class AcqImageV01:
    """Store-backed AcqImage with ROI CRUD and metadata payload roundtrip."""

    key: str
    pixel_store: PixelStore
    artifact_store: ArtifactStore
    path: str | None = None

    def __post_init__(self) -> None:
        self._img_by_channel: dict[int, np.ndarray] = {}
        self._metadata_payload_cache: dict[str, Any] | None = None
        self._metadata_dirty: bool = False

        self._header: Any | None = None
        self._experiment_metadata: Any | None = None
        self._roi_set: Any | None = None

    # ---- Constructors ----
    @classmethod
    def from_path(cls, path: str | Path) -> "AcqImageV01":
        """Create an AcqImageV01 from a TIFF file path (primary channel-1 key)."""
        p = Path(path).resolve()
        px, art = stores_for_path(p)
        return cls(key=str(p), pixel_store=px, artifact_store=art, path=str(p))

    @classmethod
    def from_zarr(cls, dataset_path: str | Path, image_id: str) -> "AcqImageV01":
        """Create an AcqImageV01 backed by a Zarr record."""
        p = Path(dataset_path).resolve()
        px, art = stores_for_path(p)
        return cls(key=str(image_id), pixel_store=px, artifact_store=art, path=str(p))

    # ---- Pixels ----
    def loadChannelData(self, channel: int = 1) -> None:
        """Eagerly load pixels for a channel into cache."""
        if channel in self._img_by_channel:
            return
        arr = self.pixel_store.load_channel(self.key, channel)
        self._img_by_channel[channel] = arr

    def getChannelData(self, channel: int = 1) -> np.ndarray:
        """Return pixels for a channel (loads on first access)."""
        self.loadChannelData(channel)
        return self._img_by_channel[channel]

    def channels_available(self) -> list[int]:
        """Return available channel keys for this image."""
        discover = getattr(self.pixel_store, "discover_channel_paths", None)
        if callable(discover):
            out = discover(self.key)
            if out:
                return sorted(int(k) for k in out.keys())
        if self._img_by_channel:
            return sorted(int(k) for k in self._img_by_channel.keys())
        return [1]

    def getChannelKeys(self) -> list[int]:
        """Back-compat for legacy AcqImage API."""
        return self.channels_available()

    def get_img_slice(self, slice_num: int = 0, channel: int = 1) -> np.ndarray | None:
        """Back-compat 2D view used by ROI stats helpers."""
        try:
            arr = self.getChannelData(channel)
        except (KeyError, ValueError):
            return None
        if arr.ndim == 2:
            return arr
        if arr.ndim >= 3:
            if slice_num < 0 or slice_num >= arr.shape[0]:
                raise ValueError(f"slice_num out of range: {slice_num}")
            return arr[slice_num]
        return None

    def getImageShape(self) -> tuple[int, ...]:
        """Return image shape (without necessarily loading pixels)."""
        info = self.pixel_store.describe(self.key)
        return info.shape

    def getImageDtype(self) -> str:
        """Return image dtype as string."""
        info = self.pixel_store.describe(self.key)
        return info.dtype

    def get_image_bounds(self) -> Any:
        """Return ImageBounds-like object if kymflow is installed, else a dict."""
        info = self.pixel_store.describe(self.key)
        axes = list(info.axes) if info.axes is not None else None
        shape = tuple(info.shape)

        axis_to_dim = {}
        if axes is not None and len(axes) == len(shape):
            axis_to_dim = {ax: dim for ax, dim in zip(axes, shape)}
        else:
            # fallback by ndim
            if len(shape) == 2:
                axis_to_dim = {"y": shape[0], "x": shape[1]}
            elif len(shape) == 3:
                axis_to_dim = {"z": shape[0], "y": shape[1], "x": shape[2]}
            elif len(shape) == 4:
                axis_to_dim = {"z": shape[0], "y": shape[1], "x": shape[2]}

        width = int(axis_to_dim.get("x", 0))
        height = int(axis_to_dim.get("y", 0))
        num_slices = int(axis_to_dim.get("z", 1))

        try:
            from kymflow.core.image_loaders.roi import ImageBounds  # type: ignore
            return ImageBounds(width=width, height=height, num_slices=num_slices)
        except ImportError:
            return {"width": width, "height": height, "num_slices": num_slices}

    def getImageBounds(self) -> Any:
        """Back-compat alias for legacy AcqImage API."""
        return self.get_image_bounds()

    # ---- Metadata payload ----
    def load_metadata_payload(self) -> dict[str, Any]:
        """Load the canonical metadata payload dict (artifact name 'metadata')."""
        if self._metadata_payload_cache is None:
            self._metadata_payload_cache = self.artifact_store.load_dict(self.key, "metadata", default={})
        return dict(self._metadata_payload_cache)

    def save_metadata_payload(self, payload: dict[str, Any]) -> None:
        """Save the canonical metadata payload dict (artifact name 'metadata')."""
        self._metadata_payload_cache = dict(payload)
        self.artifact_store.save_dict(self.key, "metadata", payload)
        self._metadata_dirty = False

    def mark_metadata_dirty(self) -> None:
        """Mark metadata/ROI state as dirty."""
        self._metadata_dirty = True

    @property
    def is_metadata_dirty(self) -> bool:
        """Return True if metadata has unsaved changes."""
        return self._metadata_dirty

    # ---- kymflow object getters/setters ----
    def getHeader(self) -> Any:
        """Return AcqImgHeader object (loads from payload if needed)."""
        _require_kymflow()
        if self._header is None:
            from kymflow.core.image_loaders.metadata import AcqImgHeader  # type: ignore
            payload = self.load_metadata_payload()
            self._header = AcqImgHeader.from_dict(payload.get("header", {}))  # type: ignore[attr-defined]
        return self._header

    def setHeader(self, header: Any) -> None:
        """Set AcqImgHeader object."""
        _require_kymflow()
        self._header = header

    def getExperimentMetadata(self) -> Any:
        """Return ExperimentMetadata object (loads from payload if needed)."""
        _require_kymflow()
        if self._experiment_metadata is None:
            from kymflow.core.image_loaders.metadata import ExperimentMetadata  # type: ignore
            payload = self.load_metadata_payload()
            self._experiment_metadata = ExperimentMetadata.from_dict(payload.get("experiment_metadata", {}))  # type: ignore[attr-defined]
        return self._experiment_metadata

    def setExperimentMetadata(self, emd: Any) -> None:
        """Set ExperimentMetadata object."""
        _require_kymflow()
        self._experiment_metadata = emd

    # ---- ROI CRUD ----
    def _ensure_roiset(self) -> Any:
        _require_kymflow()
        if self._roi_set is None:
            from kymflow.core.image_loaders.roi import RoiSet  # type: ignore
            # RoiSet expects an AcqImage-like object with get_image_bounds; we provide self
            self._roi_set = RoiSet(self)  # type: ignore[arg-type]
            # populate from payload if present
            payload = self.load_metadata_payload()
            if payload.get("rois"):
                rois_raw = payload.get("rois", [])
                if not isinstance(rois_raw, list):
                    raise TypeError("metadata payload key 'rois' must be a list")
                self._roi_set = RoiSet.from_list(rois_raw, self)  # type: ignore[arg-type]
                if hasattr(self._roi_set, "clamp"):
                    self._roi_set.clamp()
        return self._roi_set

    def rois(self) -> Any:
        """Return the RoiSet."""
        return self._ensure_roiset()

    def add_roi(self, bounds: Any, *, channel: int = 1, z: int = 0, name: str = "", note: str = "") -> int:
        """Add ROI and return its id."""
        rs = self._ensure_roiset()
        roi = rs.create_roi(bounds, channel=channel, z=z, name=name, note=note)  # type: ignore[attr-defined]
        return int(roi.id)  # type: ignore[attr-defined]

    def delete_roi(self, roi_id: int) -> bool:
        """Delete ROI by id."""
        rs = self._ensure_roiset()
        return bool(rs.delete(roi_id))  # type: ignore[attr-defined]

    def edit_roi(self, roi_id: int, **changes: Any) -> bool:
        """Edit ROI fields by id."""
        rs = self._ensure_roiset()
        roi = rs.get(roi_id)  # type: ignore[attr-defined]
        if roi is None:
            return False
        for k, v in changes.items():
            if hasattr(roi, k):
                setattr(roi, k, v)
        # clamp bounds if edited
        if hasattr(rs, "clamp"):
            rs.clamp()
        return True

    def get_roi(self, roi_id: int) -> Any | None:
        """Get ROI by id."""
        rs = self._ensure_roiset()
        return rs.get(roi_id)  # type: ignore[attr-defined]

    # ---- Persistence helpers ----
    def save_metadata_objects(self, *, auto_header_from_pixels: bool = True) -> None:
        """Serialize header/emd/rois into payload and save."""
        _require_kymflow()
        payload = self.load_metadata_payload()
        payload.setdefault("version", "2.0")

        hdr = self._header
        if hdr is None and auto_header_from_pixels:
            from kymflow.core.image_loaders.metadata import AcqImgHeader  # type: ignore
            arr = self.getChannelData(1)
            hdr = AcqImgHeader()
            hdr.set_shape_ndim(arr.shape, arr.ndim)  # type: ignore[attr-defined]
            hdr.init_defaults_from_shape()  # type: ignore[attr-defined]
            self._header = hdr

        if hdr is not None:
            payload["header"] = hdr.to_dict()  # type: ignore[union-attr]
        if self._experiment_metadata is not None:
            payload["experiment_metadata"] = self._experiment_metadata.to_dict()  # type: ignore[union-attr]

        rs = self._roi_set
        if rs is not None:
            payload["rois"] = rs.to_list()  # type: ignore[union-attr]

        self.save_metadata_payload(payload)

    def ingest_into_dataset(self, ds: Any) -> Any:
        """Convenience wrapper: ds.ingest_image(self)."""
        return ds.ingest_image(self)
