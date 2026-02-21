"""Dataset-level viewer table builder."""

from __future__ import annotations

from dataclasses import asdict
import re

import pandas as pd

from kymflow_zarr import ZarrDataset

from .record_summary import summarize_record


def _suffix(name: str) -> str:
    """Normalize a table name for DataFrame column suffixes."""
    return re.sub(r"[^0-9A-Za-z_]+", "_", str(name)).strip("_")


def build_dataset_view_table(ds: ZarrDataset, *, include_tables: list[str] | None = None) -> pd.DataFrame:
    """Build one-row-per-image viewer table.

    Args:
        ds: Backing dataset.
        include_tables: Optional dataset table names to aggregate by `image_id`.

    Returns:
        DataFrame with one row per image and summary columns plus optional
        per-table `n_rows_<table>` aggregates.
    """
    rows: list[dict[str, object]] = []
    for rec in ds.iter_records(order_by="acquired_local_epoch_ns"):
        rows.append(asdict(summarize_record(rec)))

    out = pd.DataFrame(rows)
    if len(out) == 0:
        return pd.DataFrame(
            columns=[
                "image_id",
                "original_path",
                "acquired_local_epoch_ns",
                "shape",
                "dtype",
                "axes",
                "n_rois",
                "notes",
                "has_metadata",
                "has_rois",
                "has_header",
            ]
        )

    out = out.sort_values(
        by=["acquired_local_epoch_ns", "image_id"],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)

    table_names = list(include_tables or [])
    for table_name in table_names:
        col = f"n_rows_{_suffix(table_name)}"
        out[col] = 0
        try:
            table = ds.load_table(table_name)
        except FileNotFoundError:
            continue

        if len(table) == 0 or "image_id" not in table.columns:
            continue

        counts = table.groupby("image_id", as_index=False).size().rename(columns={"size": col})
        counts["image_id"] = counts["image_id"].astype(str)
        out = out.merge(counts, on="image_id", how="left", suffixes=("", "_dup"))
        if f"{col}_dup" in out.columns:
            out[col] = out[f"{col}_dup"].fillna(out[col]).astype(int)
            out = out.drop(columns=[f"{col}_dup"])
        else:
            out[col] = out[col].fillna(0).astype(int)

    return out
