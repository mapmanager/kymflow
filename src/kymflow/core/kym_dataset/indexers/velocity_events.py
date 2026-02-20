"""Velocity event indexer for KymDataset."""

from __future__ import annotations

import logging

import pandas as pd

from kymflow_zarr import ZarrImageRecord

from ..indexer_base import BaseIndexer
from ..provenance import params_hash as compute_params_hash

logger = logging.getLogger(__name__)


class VelocityEventIndexer(BaseIndexer):
    """Build `kym_velocity_events` table rows from per-image velocity artifacts."""

    name = "velocity_events"

    def analysis_version(self) -> str:
        """Return analysis implementation version string."""
        return "kymflow.velocity_events@0.1"

    def _load_params(self, rec: ZarrImageRecord) -> dict:
        candidates = [
            "velocity_events/params",
            "velocity_events_params",
            "velocity_events.params",
        ]
        for name in candidates:
            try:
                payload = rec.load_json(name)
                if isinstance(payload, dict):
                    return payload
            except (KeyError, FileNotFoundError):
                continue
        return {}

    def params_hash(self, rec: ZarrImageRecord) -> str:
        """Compute deterministic params hash for this record."""
        params = self._load_params(rec)
        return compute_params_hash(params)

    def _load_events_df(self, rec: ZarrImageRecord) -> pd.DataFrame:
        parquet_candidates = [
            "velocity_events/events",
            "velocity_events",
        ]
        for name in parquet_candidates:
            try:
                return rec.load_df_parquet(name)
            except (KeyError, FileNotFoundError, RuntimeError):
                continue

        csv_candidates = [
            "velocity_events/events",
            "velocity_events",
        ]
        for name in csv_candidates:
            try:
                return rec.load_df_csv_gz(name)
            except (KeyError, FileNotFoundError):
                continue

        return pd.DataFrame()

    def extract_rows(self, rec: ZarrImageRecord) -> pd.DataFrame:
        """Extract velocity event rows for one image.

        Args:
            rec: Image record.

        Returns:
            DataFrame containing event rows for this image. Provenance columns are
            included and may be overwritten by `KymDataset.update_index`.
        """
        out = self._load_events_df(rec).copy()

        # Normalize some expected event columns when absent.
        event_cols = ["roi_id", "event_id", "t_start_s", "t_end_s", "peak_t_s", "peak_value", "score"]
        for col in event_cols:
            if col not in out.columns:
                out[col] = pd.NA

        out["image_id"] = rec.image_id
        out["analysis_version"] = self.analysis_version()
        out["params_hash"] = self.params_hash(rec)
        return out
