"""KymDataset v0.1 index orchestration over `kymflow_zarr` storage."""

from __future__ import annotations

import re
from typing import Any, Literal

import pandas as pd

from kymflow.core.utils.logging import get_logger
from kymflow_zarr import ZarrDataset

from .indexer_base import BaseIndexer
from .run_marker import make_run_marker, marker_matches, marker_n_rows, validate_run_marker
from .staleness import StalenessReason, StalenessResult

logger = get_logger(__name__)

_VALID_INDEXER_RE = re.compile(r"^[a-z0-9_]+$")
_RESERVED_PREFIXES = ("kym_", "tables/", "index/")


class KymDataset:
    """Domain-level dataset index updater for kym tables.

    Args:
        ds: Backing storage dataset.
    """

    def __init__(self, ds: ZarrDataset):
        self.ds = ds
        self.last_update_stats: dict[str, int] = {
            "updated": 0,
            "skipped_fresh": 0,
            "skipped_zero_rows": 0,
            "stale_missing_marker": 0,
            "stale_marker_table_mismatch": 0,
            "total_images": 0,
        }

    def _table_name(self, indexer: BaseIndexer) -> str:
        """Validate an indexer name and produce its table name.

        Args:
            indexer: Indexer implementation.

        Returns:
            Table name in the `kym_<name>` namespace.

        Raises:
            ValueError: If indexer name is invalid or reserved.
        """
        name = str(indexer.name).strip().lower()
        if not name:
            raise ValueError("Indexer name must not be empty")
        if any(name.startswith(prefix) for prefix in _RESERVED_PREFIXES):
            raise ValueError(f"Indexer name uses reserved prefix: {name}")
        if not _VALID_INDEXER_RE.fullmatch(name):
            raise ValueError(f"Indexer name must match [_a-z0-9]+, got: {indexer.name}")

        table_name = f"kym_{name}"
        if not table_name.startswith("kym_"):
            raise ValueError(f"Refusing to write non-kym table: {table_name}")
        return table_name

    def _normalize_rows(self, rows: pd.DataFrame, *, image_id: str, analysis_version: str, params_hash: str) -> pd.DataFrame:
        """Normalize one-image rows and enforce provenance columns.

        Args:
            rows: Raw extracted rows.
            image_id: Target image id for replacement.
            analysis_version: Version string to write.
            params_hash: Parameter hash to write.

        Returns:
            Normalized DataFrame suitable for replace_rows_for_image_id.
        """
        out = rows.copy()
        out["image_id"] = str(image_id)
        out["analysis_version"] = str(analysis_version)
        out["params_hash"] = str(params_hash)
        return out

    def _load_standard_run_marker(self, rec: Any, indexer_name: str) -> dict[str, object] | None:
        """Load standard run marker for an indexer.

        Args:
            rec: Record object implementing `load_json`.
            indexer_name: Indexer logical name.

        Returns:
            Marker dict or None if missing/invalid.
        """
        try:
            payload = rec.load_json(f"{indexer_name}_run")
        except (KeyError, FileNotFoundError):
            return None
        if isinstance(payload, dict):
            out = dict(payload)
            try:
                validate_run_marker(out)
            except ValueError:
                return None
            return out
        return None

    def _write_standard_run_marker(
        self,
        rec: Any,
        *,
        indexer_name: str,
        params_hash: str,
        analysis_version: str,
        n_rows: int,
    ) -> None:
        """Write standard analysis-run marker.

        Args:
            rec: Record object implementing `save_json`.
            indexer_name: Indexer logical name.
            params_hash: Deterministic params hash.
            analysis_version: Analysis version string.
            n_rows: Number of output rows emitted for this image.
        """
        rec.save_json(
            f"{indexer_name}_run",
            make_run_marker(
                indexer_name=str(indexer_name),
                params_hash=str(params_hash),
                analysis_version=str(analysis_version),
                n_rows=int(n_rows),
            ),
        )

    def get_staleness(
        self,
        table_name: str,
        image_id: str,
        params_hash: str,
        *,
        analysis_version: str,
        indexer: BaseIndexer | None = None,
        rec: Any | None = None,
    ) -> StalenessResult:
        """Compute per-image staleness diagnostics.

        Args:
            table_name: Dataset table name.
            image_id: Record image id.
            params_hash: Current params hash.
            analysis_version: Current analysis version.
            indexer: Optional indexer used to load custom marker.
            rec: Optional preloaded record.

        Returns:
            Typed staleness result.
        """
        try:
            existing = self.ds.load_table(table_name)
        except FileNotFoundError:
            existing = pd.DataFrame()

        prev = pd.DataFrame()
        if len(existing) and "image_id" in existing.columns:
            prev = existing[existing["image_id"] == image_id]
        table_rows_present = bool(len(prev) > 0)

        if rec is None:
            rec = self.ds.record(image_id)

        marker: dict[str, object] | None = None
        if indexer is not None:
            load_marker = getattr(indexer, "load_run_marker", None)
            if callable(load_marker):
                marker = load_marker(rec)
        if marker is None and indexer is not None:
            marker = self._load_standard_run_marker(rec, str(indexer.name))

        has_run_marker = bool(isinstance(marker, dict))
        marker_rows = marker_n_rows(marker)
        marker_params_match = marker_matches(marker, params_hash=str(params_hash), analysis_version=str(analysis_version))

        table_params_match = False
        table_version_match = False
        if table_rows_present and {"params_hash", "analysis_version"}.issubset(prev.columns):
            table_params_match = bool((prev["params_hash"].astype(str) == str(params_hash)).all())
            table_version_match = bool((prev["analysis_version"].astype(str) == str(analysis_version)).all())

        marker_params_only_match = False
        marker_version_match = False
        if marker is not None:
            marker_params_only_match = str(marker.get("params_hash", "")) == str(params_hash)
            marker_version_match = str(marker.get("analysis_version", "")) == str(analysis_version)

        params_hash_matches = table_params_match or marker_params_only_match
        analysis_version_matches = table_version_match or marker_version_match

        reason = StalenessReason.STALE_UNKNOWN
        is_stale = True

        if table_rows_present:
            if marker_params_match and marker_rows == 0:
                reason = StalenessReason.STALE_MARKER_TABLE_MISMATCH
            elif table_params_match and table_version_match:
                reason = StalenessReason.FRESH_ROWS
                is_stale = False
            elif not analysis_version_matches:
                reason = StalenessReason.STALE_VERSION_CHANGED
            elif not params_hash_matches:
                reason = StalenessReason.STALE_PARAMS_CHANGED
        else:
            if marker_params_match and marker_rows == 0:
                reason = StalenessReason.FRESH_ZERO_ROWS
                is_stale = False
            elif not has_run_marker:
                reason = StalenessReason.STALE_MISSING_MARKER
            elif marker_rows is not None and marker_rows > 0:
                reason = StalenessReason.STALE_MARKER_TABLE_MISMATCH
            elif not analysis_version_matches:
                reason = StalenessReason.STALE_VERSION_CHANGED
            elif not params_hash_matches:
                reason = StalenessReason.STALE_PARAMS_CHANGED

        return StalenessResult(
            image_id=str(image_id),
            table_name=str(table_name),
            has_run_marker=has_run_marker,
            table_rows_present=table_rows_present,
            marker_n_rows=marker_rows,
            params_hash_matches=params_hash_matches,
            analysis_version_matches=analysis_version_matches,
            is_stale=is_stale,
            reason=reason,
        )

    def update_index(self, indexer: BaseIndexer, *, mode: Literal["replace", "incremental"] = "replace") -> None:
        """Update one kym index table for all images.

        Args:
            indexer: Indexer implementation.
            mode: Update mode (`"replace"` or `"incremental"`).

        Raises:
            ValueError: If mode or indexer name is invalid.
            TypeError: If indexer returns a non-DataFrame.
        """
        if mode not in {"replace", "incremental"}:
            raise ValueError(
                f"Unsupported mode '{mode}'. v0.1 supports mode='replace' or mode='incremental'."
            )

        table_name = self._table_name(indexer)
        image_ids = self.ds.list_image_ids()
        stats = {
            "updated": 0,
            "skipped_fresh": 0,
            "skipped_zero_rows": 0,
            "stale_missing_marker": 0,
            "stale_marker_table_mismatch": 0,
            "total_images": len(image_ids),
        }

        try:
            existing_table = self.ds.load_table(table_name)
        except FileNotFoundError:
            existing_table = pd.DataFrame()

        for image_id in image_ids:
            rec = self.ds.record(image_id)
            params_hash = str(indexer.params_hash(rec))
            analysis_version = str(indexer.analysis_version())

            if mode == "incremental":
                staleness = self.get_staleness(
                    table_name,
                    image_id,
                    params_hash,
                    analysis_version=analysis_version,
                    indexer=indexer,
                    rec=rec,
                )
                if not staleness.is_stale:
                    if staleness.reason == StalenessReason.FRESH_ROWS:
                        stats["skipped_fresh"] += 1
                    elif staleness.reason == StalenessReason.FRESH_ZERO_ROWS:
                        stats["skipped_zero_rows"] += 1
                    else:
                        stats["skipped_fresh"] += 1
                    continue
                if staleness.reason == StalenessReason.STALE_MISSING_MARKER:
                    stats["stale_missing_marker"] += 1
                if staleness.reason == StalenessReason.STALE_MARKER_TABLE_MISMATCH:
                    stats["stale_marker_table_mismatch"] += 1

            rows = indexer.extract_rows(rec)
            if not isinstance(rows, pd.DataFrame):
                raise TypeError(f"Indexer {indexer.name} must return pandas.DataFrame")

            normalized = self._normalize_rows(
                rows,
                image_id=image_id,
                analysis_version=analysis_version,
                params_hash=params_hash,
            )

            self.ds.replace_rows_for_image_id(
                table_name,
                image_id,
                normalized,
                image_id_col="image_id",
            )
            write_marker = getattr(indexer, "write_run_marker", None)
            if callable(write_marker):
                write_marker(
                    rec,
                    params_hash=params_hash,
                    analysis_version=analysis_version,
                    n_rows=int(len(normalized)),
                )
            else:
                self._write_standard_run_marker(
                    rec,
                    indexer_name=str(indexer.name),
                    params_hash=params_hash,
                    analysis_version=analysis_version,
                    n_rows=int(len(normalized)),
                )

            # Keep local snapshot aligned for per-loop staleness decisions.
            if len(existing_table) and "image_id" in existing_table.columns:
                existing_table = existing_table[existing_table["image_id"] != image_id].copy()
            else:
                existing_table = pd.DataFrame(columns=list(normalized.columns))

            if len(normalized) == 0:
                pass
            elif len(existing_table) == 0:
                existing_table = normalized.copy()
            else:
                existing_table = pd.concat([existing_table, normalized], ignore_index=True)
            stats["updated"] += 1

        self.last_update_stats = stats
        logger.info(
            (
                "update_index indexer=%s mode=%s table=%s "
                "updated=%d skipped_fresh=%d skipped_zero_rows=%d "
                "stale_missing_marker=%d stale_marker_table_mismatch=%d total_images=%d"
            ),
            indexer.name,
            mode,
            table_name,
            stats["updated"],
            stats["skipped_fresh"],
            stats["skipped_zero_rows"],
            stats["stale_missing_marker"],
            stats["stale_marker_table_mismatch"],
            stats["total_images"],
        )
