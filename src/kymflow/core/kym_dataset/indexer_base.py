"""Indexer protocol for KymDataset table extraction."""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from kymflow_zarr import ZarrImageRecord


class BaseIndexer(Protocol):
    """Protocol for per-image index extraction.

    Implementations must extract rows for a single image record only.
    Returned rows are expected to include provenance columns:
    `image_id`, `analysis_version`, and `params_hash`.
    """

    name: str

    def extract_rows(self, rec: ZarrImageRecord) -> pd.DataFrame:
        """Extract rows for one image record.

        Args:
            rec: Image record to index.

        Returns:
            DataFrame containing rows for this image only.
        """

    def params_hash(self, rec: ZarrImageRecord) -> str:
        """Return a deterministic hash of analysis parameters for this record.

        Args:
            rec: Image record to hash parameters for.

        Returns:
            Stable hash string.
        """

    def analysis_version(self) -> str:
        """Return analysis implementation version string.

        Returns:
            Version identifier for provenance.
        """
