"""Typed staleness model for KymDataset incremental indexing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StalenessReason(StrEnum):
    """Stable reason codes for per-image staleness decisions."""

    FRESH_ROWS = "FRESH_ROWS"
    FRESH_ZERO_ROWS = "FRESH_ZERO_ROWS"
    STALE_MISSING_MARKER = "STALE_MISSING_MARKER"
    STALE_PARAMS_CHANGED = "STALE_PARAMS_CHANGED"
    STALE_VERSION_CHANGED = "STALE_VERSION_CHANGED"
    STALE_MARKER_TABLE_MISMATCH = "STALE_MARKER_TABLE_MISMATCH"
    STALE_UNKNOWN = "STALE_UNKNOWN"


@dataclass(frozen=True)
class StalenessResult:
    """Computed staleness status for one image + one index table."""

    image_id: str
    table_name: str
    has_run_marker: bool
    table_rows_present: bool
    marker_n_rows: int | None
    params_hash_matches: bool
    analysis_version_matches: bool
    is_stale: bool
    reason: StalenessReason
