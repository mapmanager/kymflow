"""Velocity event indexer for KymDataset."""

from __future__ import annotations

import pandas as pd

from kymflow.core.utils.logging import get_logger
from kymflow_zarr import ZarrImageRecord

from ..indexer_base import BaseIndexer
from ..provenance import params_hash as compute_params_hash
from ..run_marker import make_run_marker, validate_run_marker

logger = get_logger(__name__)

_MARKER_KEY = "velocity_events/summary"
_PARAMS_KEY = "velocity_events/params"
_EVENTS_KEY = "velocity_events/events"
_EVENT_COLUMNS = ["roi_id", "event_id", "t_start_s", "t_end_s", "peak_t_s", "peak_value", "score"]


class VelocityEventIndexer(BaseIndexer):
    """Build `kym_velocity_events` table rows from per-image velocity artifacts."""

    name = "velocity_events"

    def analysis_version(self) -> str:
        """Return analysis implementation version string."""
        return "kymflow.velocity_events@0.1"

    def _load_params(self, rec: ZarrImageRecord) -> dict:
        candidates = [
            _PARAMS_KEY,
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
            _EVENTS_KEY,
            "velocity_events",
        ]
        for name in parquet_candidates:
            try:
                return rec.load_df_parquet(name)
            except (KeyError, FileNotFoundError, RuntimeError):
                continue

        csv_candidates = [
            _EVENTS_KEY,
            "velocity_events",
        ]
        for name in csv_candidates:
            try:
                return rec.load_df_csv_gz(name)
            except (KeyError, FileNotFoundError):
                continue

        return pd.DataFrame(columns=list(_EVENT_COLUMNS))

    def load_run_marker(self, rec: ZarrImageRecord) -> dict[str, object] | None:
        """Load velocity event run marker from summary artifact."""
        try:
            payload = rec.load_json(_MARKER_KEY)
        except (KeyError, FileNotFoundError):
            return None
        if not isinstance(payload, dict):
            return None

        out = dict(payload)
        if "marker_version" not in out and "n_events" in out:
            out = make_run_marker(
                indexer_name=self.name,
                params_hash=str(out.get("params_hash", "")),
                analysis_version=str(out.get("analysis_version", "")),
                n_rows=int(out.get("n_events", 0)),
                ran_utc_epoch_ns=int(out.get("computed_utc_epoch_ns", 1)),
                status=str(out.get("status", "ok")),
            )

        try:
            validate_run_marker(out)
        except ValueError:
            logger.warning("Ignoring invalid velocity run marker for image_id=%s", rec.image_id)
            return None
        return out

    def write_run_marker(
        self,
        rec: ZarrImageRecord,
        *,
        params_hash: str,
        analysis_version: str,
        n_rows: int,
    ) -> None:
        """Write per-record run marker used by incremental skip logic."""
        rec.save_json(
            _MARKER_KEY,
            make_run_marker(
                indexer_name=self.name,
                params_hash=params_hash,
                analysis_version=analysis_version,
                n_rows=n_rows,
            ),
        )

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
        event_cols = list(_EVENT_COLUMNS)
        for col in event_cols:
            if col not in out.columns:
                out[col] = pd.NA

        out["image_id"] = rec.image_id
        out["analysis_version"] = self.analysis_version()
        out["params_hash"] = self.params_hash(rec)
        extra_cols = [c for c in out.columns if c not in (event_cols + ["image_id", "analysis_version", "params_hash"])]
        ordered = event_cols + extra_cols + ["image_id", "analysis_version", "params_hash"]
        return out[ordered]
