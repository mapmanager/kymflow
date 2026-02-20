"""Demo: legacy folder ingest + export using Zarr as system of record.

Run from repo root:
    uv run python src/kymflow/core/zarr/examples/demo_export_import_v01.py
"""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path
import json
import tempfile

import numpy as np
import pandas as pd

from kymflow_zarr import ZarrDataset


def _require_tifffile():
    try:
        import tifffile  # type: ignore
        return tifffile
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("This demo requires tifffile") from e


def main() -> None:
    tifffile = _require_tifffile()

    root = Path(tempfile.mkdtemp(prefix="kymflow_zarr_export_import_"))
    legacy = root / "legacy_input"
    export = root / "legacy_export"
    ds_path = root / "dataset.zarr"
    legacy.mkdir(parents=True, exist_ok=True)

    # Build a tiny legacy-style input folder.
    for i in range(2):
        stem = f"sample_{i:03d}"
        tif = legacy / f"{stem}.tif"
        arr = (np.random.rand(30, 20) * 255).astype(np.uint8)
        tifffile.imwrite(str(tif), arr)
        (legacy / f"{stem}.metadata.json").write_text(
            json.dumps({"version": "2.0", "header": {"acquired_local_epoch_ns": 100 + i}}),
            encoding="utf-8",
        )
        pd.DataFrame({"roi_id": [1], "velocity": [0.1 + i]}).to_csv(
            legacy / f"{stem}.radon_report.csv",
            index=False,
        )

    ds = ZarrDataset(str(ds_path), mode="a")
    ds.ingest_legacy_folder(legacy)
    print("Initial sources rows:", len(ds.load_sources_index()))

    # Example dataset-level table cache.
    ids = ds.list_image_ids()
    ds.save_table("velocity_events", pd.DataFrame({"image_id": ids, "event_id": [f"e{i}" for i in range(len(ids))]}))

    # Explicit refresh ingest: add one new TIFF and ingest only new files.
    new_tif = legacy / "sample_999.tif"
    tifffile.imwrite(str(new_tif), (np.random.rand(30, 20) * 255).astype(np.uint8))
    (legacy / "sample_999.metadata.json").write_text(
        json.dumps({"version": "2.0", "header": {"acquired_local_epoch_ns": 999}}),
        encoding="utf-8",
    )
    new_ids = ds.refresh_from_folder(legacy, mode="skip")
    print("Refresh ingested image_ids:", new_ids)
    print("Sources rows after refresh:", len(ds.load_sources_index()))

    ds.export_legacy_folder(export)

    print("Dataset path:", ds_path)
    print("Legacy input:", legacy)
    print("Legacy export:", export)

    ds_ro = ZarrDataset(str(ds_path), mode="r")
    ordered = [r.image_id for r in ds_ro.iter_records(order_by="acquired_local_epoch_ns")]
    print("Ordered image IDs (acquired_local_epoch_ns):", ordered)


if __name__ == "__main__":
    main()
