"""Backward-compatible viewer DataFrame helper."""

from __future__ import annotations

import pandas as pd

from kymflow_zarr import ZarrDataset

from .viewer_table import build_dataset_view_table


def build_viewer_dataframe(
    ds: ZarrDataset,
    *,
    include_tables: list[str] | None = None,
    include_velocity_events: bool | None = None,
) -> pd.DataFrame:
    """Build a viewer DataFrame via core dataset view-table helpers.

    Args:
        ds: Backing dataset.
        include_tables: Optional list of table names to aggregate by `image_id`.
        include_velocity_events: Backward-compatible flag. When `True` or when
            unspecified and `include_tables` is not provided, includes
            `kym_velocity_events` table counts.

    Returns:
        One-row-per-image DataFrame for viewer use.
    """
    table_names = include_tables
    if table_names is None:
        if include_velocity_events is False:
            table_names = []
        else:
            table_names = ["kym_velocity_events"]

    out = build_dataset_view_table(ds, include_tables=table_names)
    if "n_rows_kym_velocity_events" in out.columns and "velocity_event_count" not in out.columns:
        out["velocity_event_count"] = out["n_rows_kym_velocity_events"]
    return out
