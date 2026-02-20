"""Demo: KymDataset + indexers (dataset-level derived tables).

Run from repo root:
    uv run python src/kymflow/core/zarr/examples/demo_kym_dataset_v01.py
"""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from kymflow.core.zarr.indexers.radon_report import RadonReportIndexer
from kymflow.core.zarr.indexers.velocity_events import VelocityEventsIndexer
from kymflow.core.zarr.kym_dataset import KymDataset
from kymflow_zarr import ZarrDataset


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="kymdataset_indexers_"))
    ds_path = root / "dataset.zarr"

    ds = ZarrDataset(str(ds_path), mode="a")
    ids: list[str] = []
    for i in range(3):
        rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))
        ids.append(rec.image_id)
        rec.save_json(
            "radon_report",
            {"mean_velocity": 0.1 + i * 0.1, "median_velocity": 0.08 + i * 0.1, "n_valid": 50 + i, "notes": f"img{i}"},
        )
        if i < 2:
            rec.save_df_parquet(
                "velocity_events",
                pd.DataFrame(
                    {
                        "roi_id": [i + 1],
                        "event_id": [f"e{i+1}"],
                        "t0_s": [0.1 + i],
                        "t1_s": [0.2 + i],
                        "kind": ["drop"],
                        "score": [0.9 - i * 0.1],
                    }
                ),
            )

    kds = KymDataset(str(ds_path), mode="a")
    ve_idx = VelocityEventsIndexer()
    rr_idx = RadonReportIndexer()

    ve = kds.rebuild(ve_idx)
    rr = kds.rebuild(rr_idx)
    print("Velocity events rows:", len(ve))
    print("Radon report rows:", len(rr))

    # Simulate edit to one record then incremental update.
    rec_edit = ds.record(ids[1])
    rec_edit.save_df_parquet(
        "velocity_events",
        pd.DataFrame(
            {
                "roi_id": [99],
                "event_id": ["edited"],
                "t0_s": [1.0],
                "t1_s": [1.5],
                "kind": ["rise"],
                "score": [0.42],
            }
        ),
    )
    updated = kds.update_image(ve_idx, ids[1])
    print("Updated velocity rows:", len(updated))
    print("Rows for edited image:", len(updated[updated["image_id"] == ids[1]]))
    print("Dataset path:", ds_path)


if __name__ == "__main__":
    main()
