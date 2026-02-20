# Filename: src/kymflow_zarr/utils.py
"""Utilities for kymflow_zarr.

Notes:
    This implementation targets Zarr v2 (e.g., `zarr<3`) + `numcodecs`.
    Analysis artifacts are stored as compressed byte blobs in the underlying store.

    Blob naming convention (examples):
        images/<image_id>/analysis/events.json
        images/<image_id>/analysis/events.json.gz   (legacy read compatibility)
        images/<image_id>/analysis/roi_table.parquet
        images/<image_id>/analysis/roi_table.csv.gz  (fallback / compatibility)

    Manifest convention:
        index/manifest.json.gz
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from dataclasses import dataclass
from io import BytesIO
import gzip
import json
import re
from typing import Any, Mapping, Optional

from numcodecs import Blosc


def default_image_compressor() -> Blosc:
    """Return a good default compressor for uint8/uint16 image data.

    Returns:
        A Blosc compressor configured with zstd + bitshuffle.
    """
    return Blosc(cname="zstd", clevel=3, shuffle=Blosc.BITSHUFFLE)


def gzip_bytes(raw: bytes) -> bytes:
    """Compress bytes using gzip."""
    buf = BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as f:
        f.write(raw)
    return buf.getvalue()


def gunzip_bytes(comp: bytes) -> bytes:
    """Decompress gzip-compressed bytes."""
    with gzip.GzipFile(fileobj=BytesIO(comp), mode="rb") as f:
        return f.read()


def json_dumps(obj: Any, *, indent: int = 2) -> bytes:
    """Serialize an object to UTF-8 JSON bytes."""
    return json.dumps(obj, indent=indent, sort_keys=False).encode("utf-8")


def json_loads(raw: bytes) -> Any:
    """Deserialize UTF-8 JSON bytes to a Python object."""
    return json.loads(raw.decode("utf-8"))


_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.\-/]+")


def normalize_id(value: str) -> str:
    """Normalize an identifier to be path-safe-ish.

    This is intentionally conservative. It does not guarantee uniqueness.
    You may prefer to define a stable id strategy (e.g. UUID, hash of path).

    Args:
        value: Arbitrary identifier (often a filename stem or logical id).

    Returns:
        Normalized id string suitable for embedding in Zarr group paths.
    """
    v = value.strip().replace("\\", "/")
    v = v.replace("..", "_")
    v = _SAFE_ID_RE.sub("_", v)
    v = v.strip("/")
    return v


def utc_now_iso() -> str:
    """Get current UTC time in ISO 8601 format with 'Z'."""
    import datetime as _dt
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def require_pyarrow() -> None:
    """Raise an informative error if pyarrow is not installed."""
    try:
        import pyarrow  # noqa: F401
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Parquet support requires 'pyarrow'. Install with: uv pip install pyarrow"
        ) from e


@dataclass(frozen=True)
class PathParts:
    """Structured paths for a single image record."""

    image_id: str

    @property
    def group(self) -> str:
        return f"images/{self.image_id}"

    @property
    def data_array(self) -> str:
        return f"{self.group}/data"

    @property
    def analysis_prefix(self) -> str:
        return f"{self.group}/analysis/"

    def analysis_key(self, filename: str) -> str:
        return f"{self.analysis_prefix}{filename}"

    @property
    def analysis_arrays_group(self) -> str:
        return f"{self.group}/analysis_arrays"

    @property
    def analysis_arrays_prefix(self) -> str:
        return f"{self.analysis_arrays_group}/"

    def analysis_array_group(self, name: str) -> str:
        return f"{self.analysis_arrays_group}/{normalize_id(name)}"

    def analysis_array_data(self, name: str) -> str:
        return f"{self.analysis_array_group(name)}/data"


def is_json_serializable(obj: Any) -> bool:
    """Best-effort check for JSON serializability."""
    try:
        json.dumps(obj)
        return True
    except (TypeError, OverflowError, RecursionError, ValueError):
        return False


def merge_dict(dst: dict[str, Any], src: Mapping[str, Any], *, overwrite: bool = True) -> dict[str, Any]:
    """Merge key/values into dst."""
    for k, v in src.items():
        if overwrite or k not in dst:
            dst[k] = v
    return dst


def local_epoch_ns_from_timestamp(ts_s: float) -> int:
    """Convert a POSIX timestamp (seconds) to epoch nanoseconds (int).

    Args:
        ts_s: POSIX timestamp in seconds.

    Returns:
        Epoch nanoseconds.
    """
    # POSIX timestamps are epoch-based; local-vs-UTC comes from how ts_s was obtained.
    # When derived from file stat times on the local machine, this is consistent for ordering.
    return int(ts_s * 1_000_000_000)


def local_epoch_ns_now() -> int:
    """Return current epoch nanoseconds."""
    import time
    return local_epoch_ns_from_timestamp(time.time())
