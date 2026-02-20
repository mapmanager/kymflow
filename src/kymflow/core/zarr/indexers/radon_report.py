"""Radon report dataset indexer."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from typing import TYPE_CHECKING, Any

import pandas as pd

from .base import ensure_image_id_column

if TYPE_CHECKING:
    from kymflow_zarr import ZarrImageRecord


class RadonReportIndexer:
    """Build dataset-level radon report table from per-image artifacts."""

    name = "radon_report"
    table_name = "radon_report"
    schema_version = "v0.1"

    def required_columns(self) -> list[str]:
        """Required columns for the radon report dataset table."""
        return ["image_id", "mean_velocity", "median_velocity", "n_valid", "notes"]

    def _from_payload(self, payload: Any) -> pd.DataFrame:
        if isinstance(payload, dict):
            return pd.DataFrame([payload])
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        return pd.DataFrame()

    def extract_rows(self, rec: "ZarrImageRecord") -> pd.DataFrame:
        """Extract rows from per-image radon report artifact."""
        df: pd.DataFrame
        try:
            df = rec.load_df_parquet("radon_report")
        except (KeyError, RuntimeError, FileNotFoundError):
            try:
                payload = rec.load_json("radon_report")
            except (KeyError, FileNotFoundError):
                return pd.DataFrame(columns=self.required_columns())
            df = self._from_payload(payload)

        out = ensure_image_id_column(df, rec.image_id)

        rename_map = {
            "vel_mean": "mean_velocity",
            "vel_median": "median_velocity",
            "vel_n_valid": "n_valid",
            "note": "notes",
        }
        out = out.rename(columns=rename_map)

        for col in self.required_columns():
            if col not in out.columns:
                out[col] = pd.NA
        return out[self.required_columns()].copy()
