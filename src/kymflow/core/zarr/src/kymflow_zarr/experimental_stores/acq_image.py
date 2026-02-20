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
    """Store-backed AcqImage with ROI CRUD and metadata payload roundtrip.

    Attributes:
        source_key: PixelStore identity for this image.
            TIFF mode: absolute path to primary channel-1 TIFF.
            Zarr mode: image_id string inside the dataset.
        pixel_store: Backend used to load pixel data.
        artifact_store: Backend used to load/save artifacts.
        path: Optional physical root path (TIFF file path or dataset path).
    """

    source_key: str
    pixel_store: PixelStore
    artifact_store: ArtifactStore
    path: str | None = None

    def __post_init__(self) -> None:
        self._img_by_channel: dict[int, np.ndarray] = {}
        self._metadata_payload_cache: dict[str, Any] | None = None

        self._header: Any | None = None
        self._experiment_metadata: Any | None = None
        self._roi_set: Any | None = None

    # ---- Constructors ----
    @classmethod
    def from_path(cls, path: str | Path) -> "AcqImageV01":
        """Create an AcqImageV01 from a TIFF file path (primary channel-1 key)."""
        p = Path(path).resolve()
        px, art = stores_for_path(p)
        return cls(source_key=str(p), pixel_store=px, artifact_store=art, path=str(p))

    @classmethod
    def from_zarr(cls, dataset_path: str | Path, image_id: str) -> "AcqImageV01":
        """Create an AcqImageV01 backed by a Zarr record."""
        p = Path(dataset_path).resolve()
        px, art = stores_for_path(p)
        return cls(source_key=str(image_id), pixel_store=px, artifact_store=art, path=str(p))

    # ---- Pixels ----
    def loadChannelData(self, channel: int = 1) -> None:
        """Eagerly load pixels for a channel into cache."""
        if channel in self._img_by_channel:
            return
        arr = self.pixel_store.load_channel(self.source_key, channel)
        self._img_by_channel[channel] = arr

    def getChannelData(self, channel: int = 1) -> np.ndarray:
        """Return pixels for a channel (loads on first access)."""
        self.loadChannelData(channel)
        return self._img_by_channel[channel]

    def get_channel(self, channel: int = 1) -> np.ndarray:
        """Return pixels for a channel."""
        return self.getChannelData(channel)

    def _get_slice_2d(self, z: int, channel: int, t: int = 0) -> np.ndarray:
        """Return a 2D `(y, x)` slice from 2D..5D arrays.

        Axis convention:
            2D: `(y, x)`
            3D: `(z, y, x)`
            4D: `(z, y, x, c)`
            5D: `(t, z, y, x, c)`

        Notes:
            For v0.1, when `t` exists and no selector is provided, callers should use `t=0`.
        """
        arr = self.getChannelData(channel)
        info = self.pixel_store.describe(self.source_key)

        axes: list[str] | None = None
        if info.axes is not None and len(info.axes) in (arr.ndim, arr.ndim + 1):
            axes = list(info.axes)
            # Some stores return channel-selected arrays with one less dim than describe().
            if len(axes) == arr.ndim + 1 and "c" in axes:
                axes.remove("c")
        if axes is None:
            fallback_axes = {
                2: ["y", "x"],
                3: ["z", "y", "x"],
                4: ["z", "y", "x", "c"],
                5: ["t", "z", "y", "x", "c"],
            }
            if arr.ndim not in fallback_axes:
                raise ValueError(f"Unsupported image ndim for 2D slice extraction: {arr.ndim}")
            axes = fallback_axes[arr.ndim]

        if "y" not in axes or "x" not in axes:
            raise ValueError(f"Cannot derive 2D slice; axes missing y/x: {axes}")

        index: list[Any] = []
        for ax, dim in zip(axes, arr.shape):
            if ax == "t":
                if t < 0 or t >= dim:
                    raise ValueError(f"t index out of range: {t} for dim {dim}")
                index.append(t)
            elif ax == "z":
                if z < 0 or z >= dim:
                    raise ValueError(f"z index out of range: {z} for dim {dim}")
                index.append(z)
            elif ax == "c":
                c_idx = channel - 1
                if c_idx < 0 or c_idx >= dim:
                    raise ValueError(f"channel out of range: {channel} for dim {dim}")
                index.append(c_idx)
            elif ax in ("y", "x"):
                index.append(slice(None))
            else:
                # Unknown axis: default to first index to preserve 2D output contract.
                index.append(0)

        out = np.asarray(arr[tuple(index)])
        if out.ndim != 2:
            raise ValueError(f"Expected 2D slice after indexing, got ndim={out.ndim} with axes={axes}")
        return out

    def get_roi_pixels(self, roi_id: int) -> np.ndarray:
        """Return ROI crop pixels for a RectROI id."""
        roi = self.get_roi(roi_id)
        if roi is None:
            raise KeyError(f"ROI not found: {roi_id}")
        if not hasattr(roi, "bounds"):
            raise NotImplementedError(f"ROI id={roi_id} is not a RectROI")

        slice_2d = self._get_slice_2d(z=int(roi.z), channel=int(roi.channel), t=0)
        y0 = max(0, min(int(roi.bounds.dim0_start), slice_2d.shape[0]))
        y1 = max(0, min(int(roi.bounds.dim0_stop), slice_2d.shape[0]))
        x0 = max(0, min(int(roi.bounds.dim1_start), slice_2d.shape[1]))
        x1 = max(0, min(int(roi.bounds.dim1_stop), slice_2d.shape[1]))
        if y0 > y1:
            y0, y1 = y1, y0
        if x0 > x1:
            x0, x1 = x1, x0
        return np.asarray(slice_2d[y0:y1, x0:x1])

    def get_roi_mask(self, roi_id: int) -> np.ndarray:
        """Return a boolean mask aligned with `get_roi_pixels(roi_id)` output."""
        pix = self.get_roi_pixels(roi_id)
        return np.ones(pix.shape, dtype=bool)

    def roi_stats(self, roi_id: int) -> dict[str, float]:
        """Compute simple reduction stats for one ROI."""
        pix = self.get_roi_pixels(roi_id)
        mask = self.get_roi_mask(roi_id)
        values = pix[mask]
        if values.size == 0:
            return {"mean": float("nan"), "std": float("nan"), "min": float("nan"), "max": float("nan"), "n": 0.0}
        return {
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "n": float(values.size),
        }

    def materialize_rect_roi_mask(self, roi_id: int, *, name: str | None = None) -> str:
        """Materialize a RectROI mask to array-artifact storage and return a mask ref.

        The mask is generated on the ROI's 2D slice shape and persisted via the backing
        artifact store if it supports array artifacts.
        """
        roi = self.get_roi(roi_id)
        if roi is None:
            raise KeyError(f"ROI not found: {roi_id}")
        if not hasattr(roi, "bounds"):
            raise NotImplementedError(f"ROI id={roi_id} is not a RectROI")

        mask = self.get_roi_mask(roi_id).astype(bool)
        artifact_name = name or f"roi_mask_{int(roi_id)}"

        save_array = getattr(self.artifact_store, "save_array_artifact", None)
        if not callable(save_array):
            raise NotImplementedError("Artifact store does not support array artifacts")
        save_array(self.source_key, artifact_name, mask, axes=["y", "x"], chunks=None)

        mask_ref = f"analysis_arrays/{artifact_name}"

        # Keep JSON metadata aware of this mask reference.
        payload = self.load_metadata_payload()
        rois_raw = payload.get("rois", [])
        if isinstance(rois_raw, list):
            for item in rois_raw:
                if not isinstance(item, dict):
                    continue
                item_id = item.get("roi_id", item.get("id"))
                if item_id is None or int(item_id) != int(roi_id):
                    continue
                roi_type = str(item.get("roi_type", "rect")).lower()
                if roi_type == "mask":
                    data_block = item.setdefault("data", {})
                    if isinstance(data_block, dict):
                        data_block["mask_ref"] = mask_ref
                else:
                    meta = item.setdefault("meta", {})
                    if isinstance(meta, dict):
                        meta["mask_ref"] = mask_ref
                break
            payload["rois"] = rois_raw
            self.save_metadata_payload(payload)

        return mask_ref

    def channels_available(self) -> list[int]:
        """Return available channel keys for this image."""
        discover = getattr(self.pixel_store, "discover_channel_paths", None)
        if callable(discover):
            out = discover(self.source_key)
            if out:
                return sorted(int(k) for k in out.keys())
        if self._img_by_channel:
            return sorted(int(k) for k in self._img_by_channel.keys())
        return [1]

    def getImageShape(self) -> tuple[int, ...]:
        """Return image shape (without necessarily loading pixels)."""
        info = self.pixel_store.describe(self.source_key)
        return info.shape

    def getImageDtype(self) -> str:
        """Return image dtype as string."""
        info = self.pixel_store.describe(self.source_key)
        return info.dtype

    def get_image_bounds(self) -> Any:
        """Return ImageBounds-like object if kymflow is installed, else a dict."""
        info = self.pixel_store.describe(self.source_key)
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

    # ---- Metadata payload ----
    def load_metadata_payload(self) -> dict[str, Any]:
        """Load the canonical metadata payload dict (artifact name 'metadata')."""
        if self._metadata_payload_cache is None:
            self._metadata_payload_cache = self.artifact_store.load_dict(self.source_key, "metadata", default={})
        return dict(self._metadata_payload_cache)

    def save_metadata_payload(self, payload: dict[str, Any]) -> None:
        """Save the canonical metadata payload dict (artifact name 'metadata')."""
        self._metadata_payload_cache = dict(payload)
        self.artifact_store.save_dict(self.source_key, "metadata", payload)

    @property
    def display_name(self) -> str:
        """Human-readable name for UI/logging.

        Returns:
            TIFF mode: basename of source path.
            Zarr mode: image_id (source_key).
        """
        p = Path(self.source_key)
        if self.path is not None and Path(self.path).suffix.lower() == ".zarr":
            return self.source_key
        if p.name:
            return p.name
        return self.source_key

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
