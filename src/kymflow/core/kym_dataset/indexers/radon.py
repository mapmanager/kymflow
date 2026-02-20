"""Radon indexer for KymDataset."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from kymflow_zarr import ZarrImageRecord

from ..indexer_base import BaseIndexer
from ..provenance import params_hash as compute_params_hash

logger = logging.getLogger(__name__)


class RadonIndexer(BaseIndexer):
    """Build `kym_radon` rows from per-image radon artifacts."""

    name = "radon"

    def analysis_version(self) -> str:
        """Return analysis implementation version string."""
        return "kymflow.radon@0.1"

    def _load_params(self, rec: ZarrImageRecord) -> dict[str, Any]:
        candidates = ["radon/params", "radon_params", "radon.params"]
        for name in candidates:
            try:
                payload = rec.load_json(name)
                if isinstance(payload, dict):
                    return dict(payload)
            except (KeyError, FileNotFoundError):
                continue
        return {}

    def _load_roi_envelopes(self, rec: ZarrImageRecord) -> list[dict[str, Any]]:
        try:
            payload = rec.load_metadata_payload()
        except FileNotFoundError:
            return []
        rois = payload.get("rois", [])
        if not isinstance(rois, list):
            return []
        out: list[dict[str, Any]] = []
        for item in rois:
            if isinstance(item, dict):
                out.append(dict(item))
        return out

    def params_hash(self, rec: ZarrImageRecord) -> str:
        """Compute params hash including ROI envelopes."""
        params = self._load_params(rec)
        payload = {
            "params": params,
            "rois": self._load_roi_envelopes(rec),
        }
        return compute_params_hash(payload)

    def _load_results_df(self, rec: ZarrImageRecord) -> pd.DataFrame:
        for name in ("radon/results", "radon_report", "radon"):
            try:
                return rec.load_df_parquet(name)
            except (KeyError, FileNotFoundError, RuntimeError):
                continue
        for name in ("radon/results", "radon"):
            try:
                return rec.load_df_csv_gz(name)
            except (KeyError, FileNotFoundError):
                continue
        return pd.DataFrame()

    def extract_rows(self, rec: ZarrImageRecord) -> pd.DataFrame:
        """Extract radon rows for one record."""
        out = self._load_results_df(rec).copy()
        if "roi_id" not in out.columns:
            out["roi_id"] = pd.NA
        out["image_id"] = rec.image_id
        out["analysis_version"] = self.analysis_version()
        out["params_hash"] = self.params_hash(rec)
        cols = [c for c in out.columns if c not in ("image_id", "analysis_version", "params_hash")]
        return out[cols + ["image_id", "analysis_version", "params_hash"]]
