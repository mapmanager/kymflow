"""Demo: RadonIndexer incremental skip and ROI-edit invalidation."""

from __future__ import annotations

from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from kymflow.core.kym_dataset.indexers.radon import RadonIndexer
from kymflow.core.kym_dataset.kym_dataset import KymDataset
from kymflow_zarr import ZarrDataset


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="kymdataset_radon_roi_"))
    ds_path = root / "dataset.zarr"
    ds = ZarrDataset(str(ds_path), mode="a")
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))

    rec.save_json("radon/params", {"window": 9, "step": 2})
    rec.save_metadata_payload(
        {
            "version": "2.0",
            "rois": [
                {
                    "roi_id": 1,
                    "roi_type": "rect",
                    "version": "1.0",
                    "name": "roi1",
                    "note": "",
                    "channel": 1,
                    "z": 0,
                    "data": {"x0": 1, "x1": 6, "y0": 2, "y1": 7},
                    "meta": {},
                }
            ],
        }
    )
    rec.save_df_parquet("radon/results", pd.DataFrame({"roi_id": [1], "velocity": [0.55]}))

    kd = KymDataset(ds)
    idx = RadonIndexer()

    kd.update_index(idx, mode="replace")
    print("replace stats:", kd.last_update_stats)

    kd.update_index(idx, mode="incremental")
    print("incremental stats (no ROI change):", kd.last_update_stats)

    md = rec.load_metadata_payload()
    md["rois"][0]["data"]["x1"] = 7
    rec.save_metadata_payload(md)

    kd.update_index(idx, mode="incremental")
    print("incremental stats (ROI edited):", kd.last_update_stats)
    print("dataset path:", ds_path)


if __name__ == "__main__":
    main()
