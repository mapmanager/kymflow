"""Helpers for building viewer-facing tables from a ZarrDataset."""

from __future__ import annotations

from typing import Any

import pandas as pd

from kymflow_zarr import ZarrDataset


def build_viewer_dataframe(ds: ZarrDataset) -> pd.DataFrame:
    """Build a viewer DataFrame from records and optional dataset tables.

    Args:
        ds: Backing dataset.

    Returns:
        DataFrame with at least `image_id`, `original_path`, and
        `acquired_local_epoch_ns`, plus optional table-derived summary columns.
    """
    rows: list[dict[str, Any]] = []
    for rec in ds.iter_records(order_by="image_id"):
        original_path = None
        acquired_ns = None
        try:
            prov = rec.load_json("provenance")
            if isinstance(prov, dict):
                original_path = prov.get("original_path", prov.get("source_primary_path"))
        except KeyError:
            pass

        try:
            md = rec.load_metadata_payload()
            hdr = md.get("header", {}) if isinstance(md, dict) else {}
            if isinstance(hdr, dict):
                acquired_ns = hdr.get("acquired_local_epoch_ns")
        except FileNotFoundError:
            pass

        rows.append(
            {
                "image_id": rec.image_id,
                "original_path": original_path,
                "acquired_local_epoch_ns": acquired_ns,
            }
        )

    df = pd.DataFrame(rows)
    if len(df) == 0:
        return pd.DataFrame(columns=["image_id", "original_path", "acquired_local_epoch_ns"])

    try:
        ve = ds.load_table("kym_velocity_events")
    except FileNotFoundError:
        return df

    if len(ve) == 0 or "image_id" not in ve.columns:
        return df

    group = ve.groupby("image_id", as_index=False)
    if "score" in ve.columns:
        summary = group.agg(
            velocity_event_count=("image_id", "count"),
            velocity_event_score_mean=("score", "mean"),
        )
    else:
        summary = group.agg(
            velocity_event_count=("image_id", "count"),
        )
    out = df.merge(summary, on="image_id", how="left")
    if "velocity_event_count" in out.columns:
        out["velocity_event_count"] = out["velocity_event_count"].fillna(0).astype(int)
    return out
