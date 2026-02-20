"""Demo: velocity events zero-result marker correctness with incremental mode."""

from __future__ import annotations

from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from kymflow.core.kym_dataset.indexers.velocity_events import VelocityEventIndexer
from kymflow.core.kym_dataset.kym_dataset import KymDataset
from kymflow.core.kym_dataset.provenance import params_hash as compute_params_hash
from kymflow_zarr import ZarrDataset


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="kymdataset_ve_empty_"))
    ds_path = root / "dataset.zarr"
    ds = ZarrDataset(str(ds_path), mode="a")
    rec = ds.add_image((np.random.rand(8, 8) * 255).astype(np.uint8))

    params = {"threshold": 0.25, "window": 5}
    rec.save_json("velocity_events/params", params)
    rec.save_df_parquet(
        "velocity_events/events",
        pd.DataFrame(columns=["roi_id", "event_id", "t_start_s", "t_end_s", "peak_t_s", "peak_value", "score"]),
    )

    idx = VelocityEventIndexer()
    VelocityEventIndexer.write_run_marker(
        rec,
        params_hash=compute_params_hash(params),
        analysis_version=idx.analysis_version(),
        n_events=0,
    )

    kd = KymDataset(ds)
    kd.update_index(idx, mode="replace")
    print("replace stats:", kd.last_update_stats)

    kd.update_index(idx, mode="incremental")
    print("incremental stats (marker-matched):", kd.last_update_stats)

    rec.save_json("velocity_events/params", {"threshold": 0.7, "window": 5})
    kd.update_index(idx, mode="incremental")
    print("incremental stats (params changed):", kd.last_update_stats)
    print("dataset path:", ds_path)


if __name__ == "__main__":
    main()
