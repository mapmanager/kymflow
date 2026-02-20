"""Run-marker schema for per-image indexer execution.

Required fields:
    marker_version: Contract version string.
    indexer_name: Logical indexer name (e.g. "velocity_events").
    params_hash: Deterministic hash for indexer parameters on this image.
    analysis_version: Version string for the analysis implementation.
    n_rows: Number of rows emitted for this image in the target table.
    ran_utc_epoch_ns: Execution timestamp in UTC epoch nanoseconds.
    status: Marker status string, default "ok".
"""

from __future__ import annotations

import time
from typing import Any


RUN_MARKER_VERSION = "1"


def make_run_marker(
    *,
    indexer_name: str,
    params_hash: str,
    analysis_version: str,
    n_rows: int,
    ran_utc_epoch_ns: int | None = None,
    status: str = "ok",
) -> dict[str, object]:
    """Build a run-marker payload in contract form."""
    ran_ns = int(time.time_ns()) if ran_utc_epoch_ns is None else int(ran_utc_epoch_ns)
    return {
        "marker_version": RUN_MARKER_VERSION,
        "indexer_name": str(indexer_name),
        "params_hash": str(params_hash),
        "analysis_version": str(analysis_version),
        "n_rows": int(n_rows),
        "ran_utc_epoch_ns": ran_ns,
        "status": str(status),
    }


def validate_run_marker(d: dict[str, object]) -> None:
    """Validate marker payload shape and field types.

    Raises:
        ValueError: If required fields are missing or invalid.
    """
    required = {
        "marker_version": str,
        "indexer_name": str,
        "params_hash": str,
        "analysis_version": str,
        "n_rows": int,
        "ran_utc_epoch_ns": int,
        "status": str,
    }
    for key, typ in required.items():
        if key not in d:
            raise ValueError(f"run marker missing required field: {key}")
        if not isinstance(d[key], typ):
            raise ValueError(f"run marker field '{key}' must be {typ.__name__}")

    if str(d["marker_version"]) != RUN_MARKER_VERSION:
        raise ValueError(
            f"run marker version mismatch: expected {RUN_MARKER_VERSION}, got {d['marker_version']}"
        )
    if int(d["n_rows"]) < 0:
        raise ValueError("run marker n_rows must be >= 0")
    if int(d["ran_utc_epoch_ns"]) <= 0:
        raise ValueError("run marker ran_utc_epoch_ns must be > 0")
    if not str(d["indexer_name"]).strip():
        raise ValueError("run marker indexer_name must be non-empty")


def marker_matches(
    d: dict[str, object] | None,
    *,
    params_hash: str,
    analysis_version: str,
) -> bool:
    """Return True when a marker is valid and matches params/version."""
    if d is None:
        return False
    try:
        validate_run_marker(d)
    except ValueError:
        return False
    return str(d["params_hash"]) == str(params_hash) and str(d["analysis_version"]) == str(analysis_version)


def marker_n_rows(d: dict[str, Any] | None) -> int | None:
    """Read marker n_rows, returning None when unavailable/invalid."""
    if d is None:
        return None
    try:
        validate_run_marker(d)
    except ValueError:
        return None
    return int(d["n_rows"])
