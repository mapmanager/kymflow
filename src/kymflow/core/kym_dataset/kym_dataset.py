"""KymDataset v0.1 index orchestration over `kymflow_zarr` storage."""

from __future__ import annotations

import logging
import re
from typing import Literal

import pandas as pd

from kymflow_zarr import ZarrDataset

from .indexer_base import BaseIndexer

logger = logging.getLogger(__name__)

_VALID_INDEXER_RE = re.compile(r"^[a-z0-9_]+$")
_RESERVED_PREFIXES = ("kym_", "tables/", "index/")


class KymDataset:
    """Domain-level dataset index updater for kym tables.

    Args:
        ds: Backing storage dataset.
    """

    def __init__(self, ds: ZarrDataset):
        self.ds = ds
        self.last_update_stats: dict[str, int] = {"updated": 0, "skipped": 0, "missing": 0}

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
        stats = {"updated": 0, "skipped": 0, "missing": 0}

        try:
            existing_table = self.ds.load_table(table_name)
        except FileNotFoundError:
            existing_table = pd.DataFrame()

        for image_id in image_ids:
            rec = self.ds.record(image_id)
            params_hash = str(indexer.params_hash(rec))
            analysis_version = str(indexer.analysis_version())

            prev = pd.DataFrame()
            if len(existing_table) and "image_id" in existing_table.columns:
                prev = existing_table[existing_table["image_id"] == image_id]

            if len(prev) == 0:
                stats["missing"] += 1
                if mode == "incremental":
                    load_marker = getattr(indexer, "load_run_marker", None)
                    if callable(load_marker):
                        marker = load_marker(rec)
                        if isinstance(marker, dict):
                            marker_hash = str(marker.get("params_hash", ""))
                            marker_version = str(marker.get("analysis_version", ""))
                            if marker_hash == params_hash and marker_version == analysis_version:
                                stats["skipped"] += 1
                                continue
            elif mode == "incremental":
                has_cols = {"params_hash", "analysis_version"}.issubset(prev.columns)
                if has_cols:
                    same_hash = bool((prev["params_hash"].astype(str) == params_hash).all())
                    same_ver = bool((prev["analysis_version"].astype(str) == analysis_version).all())
                    if same_hash and same_ver:
                        stats["skipped"] += 1
                        continue

            rows = indexer.extract_rows(rec)
            if not isinstance(rows, pd.DataFrame):
                raise TypeError(f"Indexer {indexer.name} must return pandas.DataFrame")

            normalized = self._normalize_rows(rows, image_id=image_id, analysis_version=analysis_version, params_hash=params_hash)

            self.ds.replace_rows_for_image_id(
                table_name,
                image_id,
                normalized,
                image_id_col="image_id",
            )
            stats["updated"] += 1

        self.last_update_stats = stats
        logger.info(
            "update_index indexer=%s mode=%s table=%s updated=%d skipped=%d missing=%d",
            indexer.name,
            mode,
            table_name,
            stats["updated"],
            stats["skipped"],
            stats["missing"],
        )
