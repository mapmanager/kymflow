"""Domain-level dataset orchestration for kymflow over kymflow_zarr storage."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from kymflow_zarr import ZarrDataset

from .indexers.base import DatasetIndexer, normalize_table_name

if TYPE_CHECKING:
    from kymflow_zarr import ZarrImageRecord


@dataclass
class KymDataset:
    """Dataset-level orchestration and cache for derived index tables."""

    dataset_path: str | Path
    mode: str = "a"
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.dataset_path = str(self.dataset_path)
        self.ds = ZarrDataset(self.dataset_path, mode=self.mode)

    def load_tables(self, names: list[str] | None = None) -> None:
        """Load dataset-level tables into in-memory cache.

        Args:
            names: Optional list of table names. If None, load all available tables.
        """
        table_names = names if names is not None else self.ds.list_table_names()
        for name in table_names:
            table_name = normalize_table_name(name)
            self.tables[table_name] = self.ds.load_table(table_name)

    def get_table(self, name: str) -> pd.DataFrame:
        """Get a cached table, loading it if needed."""
        table_name = normalize_table_name(name)
        if table_name not in self.tables:
            self.tables[table_name] = self.ds.load_table(table_name)
        return self.tables[table_name]

    def save_table(self, name: str) -> None:
        """Save one cached table back to dataset storage."""
        table_name = normalize_table_name(name)
        if table_name not in self.tables:
            raise KeyError(f"Table not loaded in cache: {table_name}")
        self.ds.save_table(table_name, self.tables[table_name])

    def save_all_tables(self) -> None:
        """Save all cached tables back to dataset storage."""
        for table_name in sorted(self.tables.keys()):
            self.ds.save_table(table_name, self.tables[table_name])

    def _normalize_rows(self, indexer: DatasetIndexer, df: pd.DataFrame) -> pd.DataFrame:
        required = indexer.required_columns()
        out = df.copy()
        for col in required:
            if col not in out.columns:
                out[col] = pd.NA
        return out[required].copy()

    def rebuild(self, indexer: DatasetIndexer, *, image_ids: list[str] | None = None) -> pd.DataFrame:
        """Rebuild one dataset table from per-image artifacts.

        Args:
            indexer: Dataset indexer implementation.
            image_ids: Optional subset of image IDs; if omitted, rebuild for all records.

        Returns:
            Rebuilt DataFrame.
        """
        rows: list[pd.DataFrame] = []
        target_ids = image_ids if image_ids is not None else self.ds.list_image_ids()
        for image_id in target_ids:
            rec: ZarrImageRecord = self.ds.record(image_id)
            df = indexer.extract_rows(rec)
            if len(df) == 0:
                continue
            rows.append(self._normalize_rows(indexer, df))

        merged = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=indexer.required_columns())
        table_name = normalize_table_name(indexer.table_name)
        self.ds.save_table(table_name, merged)
        self.tables[table_name] = merged
        return merged

    def update_image(self, indexer: DatasetIndexer, image_id: str) -> pd.DataFrame:
        """Update one image's rows in a dataset table.

        Args:
            indexer: Dataset indexer implementation.
            image_id: Target image ID.

        Returns:
            Full updated dataset table.
        """
        rec = self.ds.record(image_id)
        rows = self._normalize_rows(indexer, indexer.extract_rows(rec))
        table_name = normalize_table_name(indexer.table_name)

        self.ds.replace_rows_for_image_id(table_name, image_id, rows, image_id_col="image_id")
        full = self.ds.load_table(table_name)
        self.tables[table_name] = full
        return full

    def update_images(self, indexer: DatasetIndexer, image_ids: list[str]) -> pd.DataFrame:
        """Update rows for multiple images.

        Args:
            indexer: Dataset indexer implementation.
            image_ids: Image IDs to update.

        Returns:
            Full updated dataset table after all image updates.
        """
        last = pd.DataFrame(columns=indexer.required_columns())
        for image_id in image_ids:
            last = self.update_image(indexer, image_id)
        return last
