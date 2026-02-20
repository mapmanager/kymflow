"""Base indexer protocol and helpers for KymDataset."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from typing import TYPE_CHECKING, Protocol
import re

import pandas as pd

if TYPE_CHECKING:
    from kymflow_zarr import ZarrImageRecord


_SAFE_NAME_RE = re.compile(r"[^a-z0-9_]+")


class DatasetIndexer(Protocol):
    """Protocol for per-record -> dataset-table indexers."""

    name: str
    table_name: str
    schema_version: str

    def extract_rows(self, rec: "ZarrImageRecord") -> pd.DataFrame:
        """Extract dataset rows for a single record."""

    def required_columns(self) -> list[str]:
        """Return required output columns."""


def ensure_image_id_column(df: pd.DataFrame, image_id: str) -> pd.DataFrame:
    """Ensure `image_id` exists and is filled for all rows."""
    out = df.copy()
    if "image_id" not in out.columns:
        out["image_id"] = image_id
    else:
        out["image_id"] = out["image_id"].fillna(image_id)
    return out


def normalize_table_name(name: str) -> str:
    """Normalize a table name to lower-case safe tokens."""
    v = name.strip().lower()
    v = _SAFE_NAME_RE.sub("_", v)
    v = v.strip("_")
    if not v:
        raise ValueError("Table name is empty after normalization")
    return v
