# Filename: examples/ingest_example.py
"""Example usage for kymflow_zarr.

Run from repo root (after installing deps):
    uv run python examples/ingest_example.py

Dependencies:
    uv pip install "zarr<3" numcodecs pandas numpy pyarrow
"""

from kymflow.core.utils.logging import get_logger
import numpy as np
import pandas as pd

from kymflow_zarr import ZarrDataset

logger = get_logger(__name__)


def main() -> None:
    ds = ZarrDataset("my_dataset.zarr", mode="a")
    ds.validate()

    # Save an image
    img = (np.random.rand(20, 512, 512) * 65535).astype(np.uint16)
    rec = ds.record("img001")
    rec.save_array(img, chunks=(1, 512, 512), axes=["z", "y", "x"], extra_attrs={"dtype_note": "uint16 demo"})

    # Save JSON analysis
    rec.save_json("events", {"n_events": 12, "method": "baseline_drop"})

    # Save tabular analysis (Parquet)
    df = pd.DataFrame({"roi_id": [1, 2], "peak": [0.2, 0.4]})
    rec.save_df_parquet("roi_table", df)

    # Update manifest
    manifest = ds.update_manifest()
    print("Manifest images:", [im["image_id"] for im in manifest.images])

    # Load back
    img2 = rec.load_array()
    events = rec.load_json("events")
    df2 = rec.load_df_parquet("roi_table")
    print(img2.shape, events, df2.head())


if __name__ == "__main__":
    main()
