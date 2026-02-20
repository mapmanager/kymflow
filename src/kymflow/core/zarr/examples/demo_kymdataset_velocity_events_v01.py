"""Demo: KymDataset + VelocityEventIndexer replace/incremental update flow."""

from __future__ import annotations

from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from kymflow.core.kym_dataset.indexers.velocity_events import VelocityEventIndexer
from kymflow.core.kym_dataset.kym_dataset import KymDataset
from kymflow_zarr import ZarrDataset


def _add_fake_record(ds: ZarrDataset, *, threshold: float, score: float) -> str:
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))
    rec.save_json("velocity_events/params", {"threshold": threshold, "window": 7})
    rec.save_df_parquet(
        "velocity_events/events",
        pd.DataFrame(
            {
                "roi_id": [1],
                "event_id": [f"ev-{rec.image_id[:6]}"],
                "t_start_s": [0.1],
                "t_end_s": [0.2],
                "peak_t_s": [0.15],
                "peak_value": [0.9],
                "score": [score],
            }
        ),
    )
    return rec.image_id


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="kymdataset_velocity_events_"))
    ds_path = root / "dataset.zarr"
    ds = ZarrDataset(str(ds_path), mode="a")

    id1 = _add_fake_record(ds, threshold=0.2, score=0.95)
    _id2 = _add_fake_record(ds, threshold=0.25, score=0.90)

    kd = KymDataset(ds)
    idx = VelocityEventIndexer()

    kd.update_index(idx, mode="replace")
    print("replace stats:", kd.last_update_stats)

    kd.update_index(idx, mode="incremental")
    print("incremental stats (no changes):", kd.last_update_stats)

    rec1 = ds.record(id1)
    rec1.save_json("velocity_events/params", {"threshold": 0.8, "window": 7})
    kd.update_index(idx, mode="incremental")
    print("incremental stats (one params changed):", kd.last_update_stats)

    out = ds.load_table("kym_velocity_events")
    print("rows:", len(out))
    print("table key exists:", "tables/kym_velocity_events.parquet" in ds.store)
    print("dataset path:", ds_path)


if __name__ == "__main__":
    main()
