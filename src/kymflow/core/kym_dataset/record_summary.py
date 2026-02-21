"""Read-only per-record summary helpers for viewer/table use."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kymflow.core.utils.logging import get_logger
from kymflow_zarr import ZarrImageRecord
from kymflow_zarr.manifest import load_manifest


logger = get_logger(__name__)


@dataclass(frozen=True)
class RecordSummary:
    """Canonical read-only summary for a single image record."""

    image_id: str
    original_path: str | None
    acquired_local_epoch_ns: int | None
    shape: tuple[int, ...] | None
    dtype: str | None
    axes: tuple[str, ...] | None
    n_rois: int | None
    notes: str | None
    has_metadata: bool
    has_rois: bool
    has_header: bool


def _manifest_entry(rec: ZarrImageRecord) -> dict[str, Any] | None:
    """Return manifest image entry for the record, when present."""
    manifest = load_manifest(rec.store)
    if manifest is None:
        return None
    for item in manifest.images:
        if str(item.get("image_id", "")) == str(rec.image_id):
            return item
    return None


def summarize_record(rec: ZarrImageRecord) -> RecordSummary:
    """Build a read-only summary for one record.

    Args:
        rec: Image record.

    Returns:
        Canonical summary dataclass used by viewer-table helpers.
    """
    image_id = str(rec.image_id)
    original_path: str | None = None
    acquired_local_epoch_ns: int | None = None
    shape: tuple[int, ...] | None = None
    dtype: str | None = None
    axes: tuple[str, ...] | None = None
    n_rois: int | None = None
    notes: str | None = None
    has_metadata = False
    has_rois = False
    has_header = False

    entry = _manifest_entry(rec)
    if entry is not None:
        shape_raw = entry.get("shape")
        if isinstance(shape_raw, list):
            shape = tuple(int(v) for v in shape_raw)
        dtype_raw = entry.get("dtype")
        if dtype_raw is not None:
            dtype = str(dtype_raw)
        axes_raw = entry.get("axes")
        if isinstance(axes_raw, list):
            axes = tuple(str(v) for v in axes_raw)
        acquired_raw = entry.get("acquired_local_epoch_ns")
        if acquired_raw is not None:
            try:
                acquired_local_epoch_ns = int(acquired_raw)
            except (TypeError, ValueError):
                acquired_local_epoch_ns = None

    if shape is None or dtype is None:
        try:
            arr = rec.open_array()
            if shape is None:
                shape = tuple(int(v) for v in arr.shape)
            if dtype is None:
                dtype = str(arr.dtype)
        except KeyError:
            logger.debug("Missing array for summary image_id=%s", image_id)

    if axes is None:
        axes_list = rec.get_axes()
        if axes_list is not None:
            axes = tuple(str(v) for v in axes_list)

    try:
        payload = rec.load_json("provenance")
        if isinstance(payload, dict):
            path = payload.get("original_path", payload.get("source_primary_path"))
            if path is not None:
                original_path = str(path)
    except (KeyError, FileNotFoundError):
        pass

    try:
        metadata = rec.load_metadata_payload()
    except FileNotFoundError:
        metadata = None

    if isinstance(metadata, dict):
        has_metadata = True

        header = metadata.get("header")
        if isinstance(header, dict):
            has_header = True
            acquired_raw = header.get("acquired_local_epoch_ns")
            if acquired_raw is not None:
                try:
                    acquired_local_epoch_ns = int(acquired_raw)
                except (TypeError, ValueError):
                    acquired_local_epoch_ns = None

        rois = metadata.get("rois")
        if isinstance(rois, list):
            n_rois = len(rois)
            has_rois = len(rois) > 0

        exp = metadata.get("experiment_metadata")
        if isinstance(exp, dict):
            note = exp.get("notes", exp.get("note"))
            if note is not None:
                notes = str(note)

    return RecordSummary(
        image_id=image_id,
        original_path=original_path,
        acquired_local_epoch_ns=acquired_local_epoch_ns,
        shape=shape,
        dtype=dtype,
        axes=axes,
        n_rois=n_rois,
        notes=notes,
        has_metadata=has_metadata,
        has_rois=has_rois,
        has_header=has_header,
    )
