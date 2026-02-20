# Filename: src/kymflow_zarr/dataset.py
"""ZarrDataset: dataset-level API.

Provides:
  - Open/create dataset (Zarr v2 directory store)
  - Schema versioning + validation
  - ZarrImageRecord object layer
  - Dataset-level manifest (index/manifest.json.gz)

Design notes:
  - `add_image(...)` always generates a uuid4 id (v0.1 safety).
  - Deletions are explicit via `delete_image(image_id)`.
  - `ingest_image(src_img)` is a high-level ingest helper for AcqImage-like objects.
"""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass
from typing import Any, Iterator, Optional, Sequence, Literal
from uuid import uuid4

import numpy as np
import zarr
from zarr.storage import DirectoryStore

from .manifest import Manifest, load_manifest, rebuild_manifest, save_manifest
from .record import ZarrImageRecord
from .schema import DatasetSchema
from .utils import utc_now_iso


OrderBy = Literal["image_id", "created_utc", "acquired_local_epoch_ns"]


@dataclass
class ZarrDataset:
    """High-level wrapper for a Zarr v2 dataset on disk.

    Args:
        path: Path to a .zarr directory (created if mode allows).
        mode: Zarr open mode ('r', 'a', 'w').
        schema: DatasetSchema defining format name + schema_version.

    Notes:
        Root attributes used:
            format: schema.format_name
            schema_version: schema.schema_version
            created_utc, updated_utc: timestamps for bookkeeping
    """

    path: str
    mode: str = "a"
    schema: DatasetSchema = DatasetSchema()

    def __post_init__(self) -> None:
        self.store = DirectoryStore(self.path)
        self.root = zarr.open_group(store=self.store, mode=self.mode)

        if self.mode in ("a", "w"):
            now = utc_now_iso()
            self.root.attrs.setdefault("format", self.schema.format_name)
            self.root.attrs.setdefault("schema_version", int(self.schema.schema_version))
            self.root.attrs.setdefault("created_utc", now)
            self.root.attrs["updated_utc"] = now

            # Ensure top-level groups exist
            self.root.require_group("images")
            self.root.require_group("index")

    # ---- Validation ----
    def validate(self) -> None:
        """Validate dataset against schema."""
        self.schema.validate_root(self.root)

    def validate_image(self, image_id: str) -> None:
        """Validate a specific image record."""
        self.schema.validate_image_record(self.root, image_id)

    # ---- Records ----
    def record(self, image_id: str) -> ZarrImageRecord:
        """Get a ZarrImageRecord wrapper for an image id."""
        return ZarrImageRecord(self.root, image_id)

    def list_image_ids(self) -> list[str]:
        """List image ids currently present under /images."""
        images = self.root.get("images", None)
        if images is None:
            return []
        return sorted(images.group_keys())

    def iter_records(self, *, order_by: OrderBy = "image_id", missing: Literal["last", "first"] = "last") -> Iterator[ZarrImageRecord]:
        """Iterate records in a deterministic order.

        Args:
            order_by: Field to order by. Uses manifest if present.
            missing: Placement for missing sort keys (only relevant for acquired_local_epoch_ns).

        Yields:
            ZarrImageRecord objects.
        """
        m = self.load_manifest()
        if m is None:
            # fallback
            for image_id in self.list_image_ids():
                yield self.record(image_id)
            return

        def sort_key(rec: dict[str, Any]) -> Any:
            if order_by == "image_id":
                return rec.get("image_id", "")
            if order_by == "created_utc":
                return rec.get("created_utc", "") or ""
            if order_by == "acquired_local_epoch_ns":
                val = rec.get("acquired_local_epoch_ns")
                if val is None:
                    return (1 if missing == "last" else -1, 0)
                return (0, int(val))
            return rec.get("image_id", "")

        for rec_d in sorted(m.images, key=sort_key):
            yield self.record(str(rec_d["image_id"]))

    def add_image(
        self,
        arr: np.ndarray,
        *,
        axes: Sequence[str] | None = None,
        chunks: tuple[int, ...] | None = None,
    ) -> ZarrImageRecord:
        """Add a new image record (uuid4 id) and save its pixels.

        Args:
            arr: N-dimensional numpy array (2D..5D).
            axes: Optional axes labels. If omitted, inferred from arr.ndim.
            chunks: Optional chunk shape. If omitted, inferred from shape+axes.

        Returns:
            ZarrImageRecord for the newly added image.
        """
        if self.mode == "r":
            raise PermissionError("Dataset opened read-only; cannot add images")
        image_id = str(uuid4())
        rec = self.record(image_id)
        rec.save_array(arr, axes=axes, chunks=chunks, overwrite=True)
        # record created_utc is set by rec.save_array; touch dataset updated_utc too
        self._touch_updated()
        return rec

    def delete_image(self, image_id: str) -> None:
        """Delete an image record group and all its artifacts."""
        if self.mode == "r":
            raise PermissionError("Dataset opened read-only; cannot delete images")
        grp_path = f"images/{image_id}"
        if grp_path in self.root:
            del self.root[grp_path]
        # remove any remaining analysis keys in store
        prefix = f"images/{image_id}/analysis/"
        for k in list(self.store.keys()):
            if k.startswith(prefix):
                del self.store[k]
        self._touch_updated()

    def ingest_image(self, src_img: Any) -> ZarrImageRecord:
        """Ingest an AcqImage-like object into this dataset.

        The source image must provide:
            - getChannelData(channel:int=1) -> np.ndarray   (or get_channel)
            - header/experiment/roi accessors OR metadata payload

        This method is designed to be called from GUI-level code using AcqImageV01.

        Args:
            src_img: Source image object (typically AcqImageV01).

        Returns:
            The newly created record.
        """
        # pixels
        if hasattr(src_img, "getChannelData"):
            arr = src_img.getChannelData(1)
        elif hasattr(src_img, "get_channel"):
            arr = src_img.get_channel(1)
        else:
            raise TypeError("src_img must provide getChannelData(1) or get_channel(1)")

        rec = self.add_image(arr)

        # metadata objects/payload (optional)
        header = src_img.getHeader() if hasattr(src_img, "getHeader") else None
        experiment = src_img.getExperimentMetadata() if hasattr(src_img, "getExperimentMetadata") else None
        rois = src_img.rois() if hasattr(src_img, "rois") else None

        acquired_ns = None
        if header is not None and hasattr(header, "acquired_local_epoch_ns"):
            acquired_ns = getattr(header, "acquired_local_epoch_ns")

        if header is not None or experiment is not None or rois is not None:
            rec.save_metadata_objects(
                header=header,
                experiment=experiment,
                rois=rois,
                auto_header_from_array=True,
                acquired_local_epoch_ns=acquired_ns,
            )
            return rec

        if hasattr(src_img, "load_metadata_payload"):
            payload = src_img.load_metadata_payload()
            if payload:
                rec.save_metadata_payload(payload)
                return rec

        return rec

    # ---- Manifest ----
    def load_manifest(self) -> Optional[Manifest]:
        """Load manifest if present."""
        return load_manifest(self.store)

    def rebuild_manifest(self, *, include_analysis_keys: bool = True) -> Manifest:
        """Rebuild manifest by scanning dataset and store keys."""
        return rebuild_manifest(self.root, include_analysis_keys=include_analysis_keys)

    def save_manifest(self, manifest: Manifest) -> None:
        """Save manifest to store."""
        save_manifest(self.store, manifest)
        self._touch_updated()

    def update_manifest(self, *, include_analysis_keys: bool = True) -> Manifest:
        """Rebuild and save the manifest."""
        m = self.rebuild_manifest(include_analysis_keys=include_analysis_keys)
        self.save_manifest(m)
        return m

    # ---- Internals ----
    def _touch_updated(self) -> None:
        self.root.attrs["updated_utc"] = utc_now_iso()
