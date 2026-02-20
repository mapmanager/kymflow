# Filename: src/kymflow_zarr/manifest.py
"""Dataset manifest/index.

The manifest is stored as a gzipped JSON blob at:
    index/manifest.json.gz

It enables:
  - Fast traversal without scanning arrays/chunks each time
  - Ordering images in multiple ways (by created time, acquisition time, custom keys)
  - Recording artifact presence per image (json/parquet/csv.gz)

Callers do not need to use the manifest directly, but higher-level APIs may use it
for fast listing/sorting in GUIs and batch pipelines.

Design:
  - The manifest is a cache/index; it can always be rebuilt from the dataset.
  - Per-image domain metadata lives in the record's "metadata" payload artifact.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from dataclasses import dataclass
import json
from typing import Any, Optional

import zarr

from .utils import gzip_bytes, gunzip_bytes, json_dumps, json_loads, utc_now_iso


MANIFEST_KEY = "index/manifest.json.gz"


@dataclass
class Manifest:
    """In-memory manifest representation."""

    schema_version: int
    format_name: str
    created_utc: str
    updated_utc: str
    images: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "format": self.format_name,
            "created_utc": self.created_utc,
            "updated_utc": self.updated_utc,
            "images": self.images,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Manifest":
        return cls(
            schema_version=int(d.get("schema_version", 0)),
            format_name=str(d.get("format", "")),
            created_utc=str(d.get("created_utc", "")),
            updated_utc=str(d.get("updated_utc", "")),
            images=list(d.get("images", [])),
        )


def load_manifest(store: Any) -> Optional[Manifest]:
    """Load manifest from store, if present."""
    if MANIFEST_KEY not in store:
        return None
    raw = gunzip_bytes(store[MANIFEST_KEY])
    d = json_loads(raw)
    return Manifest.from_dict(d)


def save_manifest(store: Any, manifest: Manifest) -> None:
    """Save manifest to store."""
    store[MANIFEST_KEY] = gzip_bytes(json_dumps(manifest.to_dict(), indent=2))


def _extract_acquired_ns_from_metadata(store: Any, image_id: str) -> int | None:
    """Extract acquired_local_epoch_ns from metadata artifact if present.

    Read order:
        1) analysis/metadata.json
        2) legacy analysis/metadata.json.gz
    """
    key_json = f"images/{image_id}/analysis/metadata.json"
    key_gz = f"images/{image_id}/analysis/metadata.json.gz"
    try:
        if key_json in store:
            payload = json_loads(store[key_json])
        elif key_gz in store:
            payload = json_loads(gunzip_bytes(store[key_gz]))
        else:
            return None
        hdr = payload.get("header", {})
        val = hdr.get("acquired_local_epoch_ns")
        if val is None:
            return None
        return int(val)
    except (OSError, EOFError, json.JSONDecodeError, TypeError, ValueError, KeyError):
        return None


def rebuild_manifest(root: zarr.hierarchy.Group, *, include_analysis_keys: bool = True) -> Manifest:
    """Rebuild manifest by scanning the Zarr hierarchy and store keys.

    Args:
        root: Root zarr group.
        include_analysis_keys: If True, list analysis blobs for each image.

    Returns:
        A new Manifest built from current store state.
    """
    store = root.store
    fmt = str(root.attrs.get("format", ""))
    schema_version = int(root.attrs.get("schema_version", 0))

    now = utc_now_iso()
    images: list[dict[str, Any]] = []

    images_group = root.get("images", None)
    if images_group is not None:
        for image_id in sorted(images_group.group_keys()):
            grp = images_group[image_id]
            arr = grp.get("data", None)
            if arr is None:
                continue

            rec: dict[str, Any] = {
                "image_id": image_id,
                "shape": list(arr.shape),
                "dtype": str(arr.dtype),
                "chunks": list(arr.chunks) if arr.chunks is not None else None,
                "axes": list(grp.attrs.get("axes")) if grp.attrs.get("axes") is not None else None,
                "created_utc": grp.attrs.get("created_utc"),
                "updated_utc": grp.attrs.get("updated_utc"),
                "acquired_local_epoch_ns": _extract_acquired_ns_from_metadata(store, image_id),
            }

            if include_analysis_keys:
                prefix = f"images/{image_id}/analysis/"
                rec["analysis_keys"] = sorted([k for k in store.keys() if k.startswith(prefix)])
            images.append(rec)

    prev = load_manifest(store)
    created = prev.created_utc if prev is not None else now
    return Manifest(
        schema_version=schema_version,
        format_name=fmt,
        created_utc=created,
        updated_utc=now,
        images=images,
    )
