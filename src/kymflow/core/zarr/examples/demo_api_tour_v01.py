"""API tour demo for kymflow_zarr v0.1.

This script is intentionally self-contained: it creates a temporary dataset,
exercises the primary APIs, then leaves the dataset on disk for inspection.

Run from repo root:
    uv run python src/kymflow/core/zarr/examples/demo_api_tour_v01.py
"""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from kymflow_zarr import ZarrDataset
from kymflow_zarr.experimental_stores import AcqImageListV01


def print_manifest(ds: ZarrDataset, label: str) -> None:
    m = ds.update_manifest()
    print(f"\n[{label}] manifest image count:", len(m.images))
    for rec in m.images:
        print(
            "  -",
            rec["image_id"],
            "shape=",
            rec.get("shape"),
            "acquired_ns=",
            rec.get("acquired_local_epoch_ns"),
            "analysis_keys=",
            len(rec.get("analysis_keys", [])),
        )


def main() -> None:
    tmp_root = Path(tempfile.mkdtemp(prefix="kymflow_zarr_demo_"))
    ds_path = tmp_root / "api_tour.zarr"
    print("Dataset path:", ds_path)

    # 1) Create dataset and add two records with different shapes.
    ds = ZarrDataset(str(ds_path), mode="a")
    ds.validate()

    arr_a = (np.random.rand(8, 64, 64) * 65535).astype(np.uint16)
    arr_b = (np.random.rand(8, 64, 64) * 255).astype(np.uint8)

    rec_a = ds.add_image(arr_a, axes=["z", "y", "x"], chunks=(1, 64, 64))
    rec_b = ds.add_image(arr_b, axes=["z", "y", "x"], chunks=(1, 64, 64))
    print("Added records:", rec_a.image_id, rec_b.image_id)

    # 2) Save metadata payload + analysis artifacts.
    rec_a.save_metadata_payload(
        {
            "version": "2.0",
            "header": {"acquired_local_epoch_ns": 100},
            "experiment_metadata": {"group": "control"},
        }
    )
    rec_b.save_metadata_payload(
        {
            "version": "2.0",
            "header": {"acquired_local_epoch_ns": 200},
            "experiment_metadata": {"group": "treated"},
        }
    )

    rec_a.save_json("kym_analysis_summary", {"n_rois": 3, "method": "mpRadon"})
    rec_a.save_df_csv_gz(
        "roi_table",
        pd.DataFrame(
            {
                "roi_id": [1, 2, 3],
                "velocity_mean": [0.12, 0.08, 0.17],
            }
        ),
    )

    # Optional parquet save if pyarrow is available.
    try:
        rec_a.save_df_parquet(
            "roi_table_parquet",
            pd.DataFrame({"roi_id": [1], "velocity_mean": [0.12]}),
        )
    except RuntimeError as e:
        print("Parquet skipped:", e)

    # 3) Manifest and ordering.
    print_manifest(ds, "after writes")
    by_acquired = [r.image_id for r in ds.iter_records(order_by="acquired_local_epoch_ns")]
    by_created = [r.image_id for r in ds.iter_records(order_by="created_utc")]
    print("Order by acquired_local_epoch_ns:", by_acquired)
    print("Order by created_utc:", by_created)

    # 4) Read-only open + validation.
    ds_ro = ZarrDataset(str(ds_path), mode="r")
    ds_ro.validate()
    for image_id in ds_ro.list_image_ids():
        ds_ro.validate_image(image_id)
    print("Read-only validation passed for", len(ds_ro.list_image_ids()), "records")

    # 5) Traverse through AcqImageListV01 using zarr backend.
    lst = AcqImageListV01(ds_path)
    print("AcqImageListV01 over zarr records:", len(lst))
    for img in lst:
        arr = img.getChannelData(1)
        print("  image key:", img.source_key, "shape:", arr.shape, "dtype:", arr.dtype)

    # 6) Cleanup example operations: delete one analysis type + one image.
    deleted = rec_a.delete_analysis(suffixes=(".csv.gz",))
    print("Deleted CSV analysis blobs from rec_a:", deleted)
    ds.delete_image(rec_b.image_id)
    print_manifest(ds, "after delete")

    print("\nDemo complete. Dataset kept for inspection at:", ds_path)


if __name__ == "__main__":
    main()
