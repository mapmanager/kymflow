# Filename: src/kymflow_zarr/record.py
"""ZarrImageRecord: per-image object layer.

This layer owns per-record storage conventions:
  - Array location: images/<image_id>/data
  - Default axes inference for ndarrays (2D..5D):
      2D: (y, x)
      3D: (z, y, x)
      4D: (z, y, x, c)
      5D: (t, z, y, x, c)
  - Default chunking policy (safe defaults for modest microscopy volumes):
      t/z/c chunk = 1
      y/x chunk = min(dim, 512)
  - Artifacts under analysis/ (gzipped JSON, Parquet, gzipped CSV)

Notes:
    This class is storage-focused. It should NOT implement domain analysis or UI behavior.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import Any, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import zarr

from .utils import (
    PathParts,
    default_image_compressor,
    gzip_bytes,
    gunzip_bytes,
    json_dumps,
    json_loads,
    normalize_id,
    require_pyarrow,
    utc_now_iso,
)


_AXES_BY_NDIM: dict[int, tuple[str, ...]] = {
    2: ("y", "x"),
    3: ("z", "y", "x"),
    4: ("z", "y", "x", "c"),
    5: ("t", "z", "y", "x", "c"),
}

class MetadataNotFoundError(FileNotFoundError):
    """Raised when canonical metadata payload is missing for an image record."""


def _infer_axes(ndim: int) -> list[str]:
    """Infer default axes for a given ndarray dimensionality."""
    if ndim not in _AXES_BY_NDIM:
        raise ValueError(f"Unsupported ndarray ndim={ndim}; expected 2..5")
    return list(_AXES_BY_NDIM[ndim])


def _infer_chunks(shape: tuple[int, ...], axes: Sequence[str]) -> tuple[int, ...]:
    """Infer a safe default chunk shape given array shape and axes."""
    if len(shape) != len(axes):
        raise ValueError("shape/axes length mismatch")
    out: list[int] = []
    for dim, ax in zip(shape, axes):
        if ax in ("t", "z", "c"):
            out.append(1)
        elif ax in ("y", "x"):
            out.append(int(min(dim, 512)))
        else:
            # Unknown axis name: treat like spatial for now
            out.append(int(min(dim, 512)))
    return tuple(out)


@dataclass
class ZarrImageRecord:
    """A storage-focused wrapper around one image record in a ZarrDataset.

    An image record is stored at:
        images/<image_id>/

    Within that group:
        data               (zarr array)
        attrs              (bookkeeping + axes)
        analysis/*         (artifact blobs)

    Args:
        root: Root zarr group.
        image_id: Record id (normalized for on-disk paths).
    """

    root: zarr.hierarchy.Group
    image_id: str

    def __post_init__(self) -> None:
        self.image_id = normalize_id(self.image_id)
        self.parts = PathParts(self.image_id)

    # ---- Group / array access ----
    def open_group(self) -> zarr.hierarchy.Group:
        """Open record group without creating it."""
        if self.parts.group not in self.root:
            raise KeyError(f"Missing group: /{self.parts.group}")
        return self.root[self.parts.group]

    def require_group(self) -> zarr.hierarchy.Group:
        """Return (and create if needed) the record group."""
        return self.root.require_group(self.parts.group)

    @property
    def group(self) -> zarr.hierarchy.Group:
        """Return the existing record group (read-only safe; no creation)."""
        return self.open_group()

    @property
    def store(self) -> Any:
        """Return the underlying Zarr store."""
        return self.root.store

    def open_array(self) -> zarr.core.Array:
        """Open the data array for lazy access."""
        return self.root[self.parts.data_array]

    def load_array(self) -> np.ndarray:
        """Load the full image array into memory."""
        return self.open_array()[:]

    def get_axes(self) -> list[str] | None:
        """Return stored axes labels, if present."""
        try:
            ax = self.group.attrs.get("axes")
        except KeyError:
            return None
        return list(ax) if ax is not None else None

    def save_array(
        self,
        arr: np.ndarray,
        *,
        axes: Optional[Sequence[str]] = None,
        chunks: Optional[tuple[int, ...]] = None,
        compressor: Optional[Any] = None,
        overwrite: bool = True,
        extra_attrs: Optional[dict[str, Any]] = None,
    ) -> zarr.core.Array:
        """Save the image array to images/<id>/data with backend defaults.

        Args:
            arr: N-dimensional numpy array (2D..5D).
            axes: Optional axis labels. If omitted, inferred from arr.ndim using kymflow defaults.
            chunks: Optional chunk shape. If omitted, inferred from shape+axes.
            compressor: numcodecs compressor; defaults to Blosc(zstd, bitshuffle).
            overwrite: If True, replace existing array.
            extra_attrs: Additional group attrs to store.

        Returns:
            The created zarr Array.

        Raises:
            ValueError: If ndim unsupported, or axes/chunks incompatible.
        """
        grp = self.require_group()

        if compressor is None:
            compressor = default_image_compressor()

        if axes is None:
            axes_l = _infer_axes(arr.ndim)
        else:
            axes_l = list(axes)
            if len(axes_l) != arr.ndim:
                raise ValueError(f"axes length {len(axes_l)} does not match arr.ndim {arr.ndim}")

        if chunks is None:
            chunks_t = _infer_chunks(tuple(arr.shape), axes_l)
        else:
            chunks_t = tuple(chunks)
            if len(chunks_t) != arr.ndim:
                raise ValueError(f"chunks length {len(chunks_t)} does not match arr.ndim {arr.ndim}")

        if overwrite and "data" in grp:
            del grp["data"]

        z = grp.create_dataset(
            "data",
            shape=arr.shape,
            dtype=arr.dtype,
            chunks=chunks_t,
            compressor=compressor,
            overwrite=overwrite,
        )
        z[:] = arr

        now = utc_now_iso()
        grp.attrs.setdefault("created_utc", now)
        grp.attrs["updated_utc"] = now
        grp.attrs["axes"] = axes_l

        if extra_attrs:
            for k, v in extra_attrs.items():
                grp.attrs[k] = v

        return z

    # ---- Derived bounds ----
    def get_image_bounds(self) -> dict[str, int]:
        """Return image bounds derived from stored axes + shape.

        Returns:
            Dict with keys: width, height, num_slices.

        Notes:
            - width/height correspond to x/y.
            - num_slices corresponds to z when present, else 1.
            - Time and channel axes do not affect bounds.
        """
        arr = self.open_array()
        axes = self.get_axes() or _infer_axes(arr.ndim)
        shape = tuple(arr.shape)

        axis_to_dim = {ax: dim for ax, dim in zip(axes, shape)}
        width = int(axis_to_dim.get("x", 0))
        height = int(axis_to_dim.get("y", 0))
        num_slices = int(axis_to_dim.get("z", 1))
        return {"width": width, "height": height, "num_slices": num_slices}

    # ---- Metadata convenience (optional kymflow) ----
    def save_metadata_payload(self, payload: dict[str, Any]) -> str:
        """Save the canonical metadata payload under analysis/metadata.json."""
        return self.save_json("metadata", payload)

    def load_metadata_payload(self) -> dict[str, Any]:
        """Load the canonical metadata payload from analysis/metadata.json.

        Backward compatibility:
            Falls back to legacy analysis/metadata.json.gz if needed.
        """
        try:
            return dict(self.load_json("metadata"))
        except KeyError as e:
            raise MetadataNotFoundError(f"Missing metadata payload for image_id={self.image_id}") from e

    def save_metadata_objects(
        self,
        *,
        header: Any | None = None,
        experiment: Any | None = None,
        rois: Any | None = None,
        auto_header_from_array: bool = True,
        acquired_local_epoch_ns: int | None = None,
    ) -> None:
        """Save header/experiment/rois as the canonical metadata payload.

        This is an optional convenience API that uses kymflow objects if importable.
        If kymflow isn't installed, callers should use save_metadata_payload() directly.

        Args:
            header: Optional AcqImgHeader object.
            experiment: Optional ExperimentMetadata object.
            rois: Optional RoiSet object.
            auto_header_from_array: If True and header is None, create header from stored array.
            acquired_local_epoch_ns: Optional override for acquisition time stored in header.

        Raises:
            RuntimeError: If kymflow isn't importable and object conversion is requested.
        """
        try:
            from kymflow.core.image_loaders.metadata import AcqImgHeader, ExperimentMetadata  # type: ignore
            from kymflow.core.image_loaders.roi import RoiSet  # type: ignore
        except ImportError as e:  # pragma: no cover
            if header is None and experiment is None and rois is None and not auto_header_from_array:
                # payload-only path; nothing to do
                raise RuntimeError("No objects provided and auto_header_from_array=False") from e
            raise ImportError("kymflow is required for save_metadata_objects()") from e

        if header is None and auto_header_from_array:
            arr = self.open_array()
            axes = self.get_axes() or _infer_axes(arr.ndim)
            header = AcqImgHeader()
            # Back-compat: AcqImgHeader currently uses these methods
            header.set_shape_ndim(arr.shape, arr.ndim)  # type: ignore[attr-defined]
            header.init_defaults_from_shape()  # type: ignore[attr-defined]
            # Store axes if header supports it (optional)
            if hasattr(header, "axes"):
                try:
                    header.axes = list(axes)  # type: ignore[attr-defined]
                except (AttributeError, TypeError, ValueError):
                    pass

        if experiment is None:
            experiment = ExperimentMetadata()

        payload: dict[str, Any] = {"version": "2.0"}
        if header is not None:
            if acquired_local_epoch_ns is not None and hasattr(header, "acquired_local_epoch_ns"):
                header.acquired_local_epoch_ns = int(acquired_local_epoch_ns)  # type: ignore[attr-defined]
            payload["header"] = header.to_dict()  # type: ignore[union-attr]
        if experiment is not None:
            payload["experiment_metadata"] = experiment.to_dict()  # type: ignore[union-attr]
        if rois is not None:
            payload["rois"] = rois.to_list()  # type: ignore[union-attr]

        self.save_metadata_payload(payload)

    def load_metadata_objects(self) -> tuple[Any, Any, Any]:
        """Load header/experiment/rois as kymflow objects.

        Returns:
            (header, experiment, rois)

        Raises:
            RuntimeError: If kymflow isn't importable.
            KeyError: If metadata payload is missing required keys.
        """
        try:
            from kymflow.core.image_loaders.metadata import AcqImgHeader, ExperimentMetadata  # type: ignore
            from kymflow.core.image_loaders.roi import RoiSet, ImageBounds  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise ImportError("kymflow is required for load_metadata_objects()") from e

        payload = self.load_metadata_payload()
        hdr = AcqImgHeader.from_dict(payload.get("header", {}))  # type: ignore[attr-defined]
        em = ExperimentMetadata.from_dict(payload.get("experiment_metadata", {}))  # type: ignore[attr-defined]

        b = self.get_image_bounds()
        bounds = ImageBounds(width=b["width"], height=b["height"], num_slices=b["num_slices"])
        # RoiSet.from_list expects an object with get_image_bounds; provide a tiny shim internally
        class _Shim:
            def get_image_bounds(self) -> Any:
                return bounds
        rois = RoiSet.from_list(payload.get("rois", []), _Shim())  # type: ignore[arg-type]
        # Clamp defensively if method exists
        if hasattr(rois, "clamp"):
            try:
                rois.clamp()  # type: ignore[attr-defined]
            except (AttributeError, TypeError, ValueError):
                pass
        return hdr, em, rois

    # ---- JSON analysis blobs ----
    def save_json(self, name: str, obj: Any, *, indent: int = 2) -> str:
        """Save JSON analysis blob under analysis/ (canonical *.json, uncompressed)."""
        filename = f"{normalize_id(name)}.json"
        key = self.parts.analysis_key(filename)
        self.store[key] = json_dumps(obj, indent=indent)
        self._touch_updated()
        return key

    def load_json(self, name: str) -> Any:
        """Load JSON analysis blob.

        Read order:
            1) analysis/<name>.json
            2) legacy analysis/<name>.json.gz
        """
        base = normalize_id(name)
        key_json = self.parts.analysis_key(f"{base}.json")
        if key_json in self.store:
            return json_loads(self.store[key_json])

        key_gz = self.parts.analysis_key(f"{base}.json.gz")
        if key_gz in self.store:
            raw = gunzip_bytes(self.store[key_gz])
            return json_loads(raw)
        raise KeyError(key_json)

    # ---- Tabular analysis blobs ----
    def save_df_parquet(self, name: str, df: pd.DataFrame, *, compression: str = "zstd") -> str:
        """Save a DataFrame as Parquet bytes under analysis/."""
        require_pyarrow()
        filename = f"{normalize_id(name)}.parquet"
        key = self.parts.analysis_key(filename)

        buf = BytesIO()
        df.to_parquet(buf, index=False, compression=compression)
        self.store[key] = buf.getvalue()
        self._touch_updated()
        return key

    def load_df_parquet(self, name: str) -> pd.DataFrame:
        """Load a DataFrame stored as Parquet bytes."""
        require_pyarrow()
        filename = f"{normalize_id(name)}.parquet"
        key = self.parts.analysis_key(filename)
        return pd.read_parquet(BytesIO(self.store[key]))

    def save_df_csv_gz(self, name: str, df: pd.DataFrame, *, index: bool = False) -> str:
        """Save a DataFrame as gzipped CSV bytes under analysis/."""
        filename = f"{normalize_id(name)}.csv.gz"
        key = self.parts.analysis_key(filename)
        csv_text = df.to_csv(index=index)
        self.store[key] = gzip_bytes(csv_text.encode("utf-8"))
        self._touch_updated()
        return key

    def load_df_csv_gz(self, name: str) -> pd.DataFrame:
        """Load a DataFrame stored as gzipped CSV bytes."""
        filename = f"{normalize_id(name)}.csv.gz"
        key = self.parts.analysis_key(filename)
        raw = gunzip_bytes(self.store[key]).decode("utf-8")
        return pd.read_csv(StringIO(raw))

    def list_analysis_keys(self) -> list[str]:
        """List all analysis blob keys for this image."""
        prefix = self.parts.analysis_prefix
        return sorted([k for k in self.store.keys() if k.startswith(prefix)])

    def delete_analysis(self, *, suffixes: Optional[tuple[str, ...]] = None) -> int:
        """Delete analysis blobs for this image."""
        prefix = self.parts.analysis_prefix
        keys = [k for k in list(self.store.keys()) if k.startswith(prefix)]
        if suffixes is not None:
            keys = [k for k in keys if k.endswith(suffixes)]

        for k in keys:
            del self.store[k]

        if keys:
            self._touch_updated()
        return len(keys)

    def _touch_updated(self) -> None:
        """Update the record group's updated_utc timestamp."""
        grp = self.require_group()
        grp.attrs["updated_utc"] = utc_now_iso()
