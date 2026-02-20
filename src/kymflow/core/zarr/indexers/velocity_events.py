"""Velocity events dataset indexer."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from typing import TYPE_CHECKING

import pandas as pd

from .base import ensure_image_id_column

if TYPE_CHECKING:
    from kymflow_zarr import ZarrImageRecord


class VelocityEventsIndexer:
    """Build dataset-level velocity events table from per-image artifacts."""

    name = "velocity_events"
    table_name = "velocity_events"
    schema_version = "v0.1"

    def required_columns(self) -> list[str]:
        """Required columns for the velocity events dataset table."""
        return ["image_id", "roi_id", "event_id", "t0_s", "t1_s", "kind", "score"]

    def extract_rows(self, rec: "ZarrImageRecord") -> pd.DataFrame:
        """Extract rows from per-image velocity events artifact."""
        try:
            df = rec.load_df_parquet("velocity_events")
        except (KeyError, RuntimeError, FileNotFoundError):
            return pd.DataFrame(columns=self.required_columns())

        out = ensure_image_id_column(df, rec.image_id)
        for col in self.required_columns():
            if col not in out.columns:
                out[col] = pd.NA
        return out[self.required_columns()].copy()
