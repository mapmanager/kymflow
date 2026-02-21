# Workflows

## Create/Open Dataset
```python
from kymflow_zarr import ZarrDataset

ds = ZarrDataset("/tmp/my_dataset.zarr", mode="a")
```

## Ingest TIFF
```python
from pathlib import Path
import tifffile
from kymflow_zarr import ZarrDataset

ds = ZarrDataset("/tmp/my_dataset.zarr", mode="a")
arr = tifffile.imread(Path("/data/example.tif"))
rec = ds.add_image(arr)
```

## Attach Provenance JSON
```python
rec.save_json("provenance", {
    "original_path": "/data/example.tif",
    "source_primary_path": "/data/example.tif",
})
```

## Save/Load Canonical Metadata Payload
```python
rec.save_metadata_payload({
    "version": "2.0",
    "header": {"acquired_local_epoch_ns": 1730000000000000000},
    "experiment_metadata": {"notes": "pilot run"},
    "rois": [],
})

payload = rec.load_metadata_payload()
```

## Save/Load Metadata Objects (kymflow classes available)
```python
# Optional: requires kymflow metadata/ROI classes importable.
rec.save_metadata_objects(header=header, experiment=experiment, rois=rois)
header2, experiment2, rois2 = rec.load_metadata_objects()
```

## Record Artifact Tables
```python
import pandas as pd

df = pd.DataFrame({"roi_id": [1], "score": [0.98]})
rec.save_df_parquet("velocity_events/events", df)
out_df = rec.load_df_parquet("velocity_events/events")
```

## Dataset Tables
```python
import pandas as pd

ds.save_table("kym_velocity_events", pd.DataFrame({"image_id": [rec.image_id], "score": [0.98]}))
table_df = ds.load_table("kym_velocity_events")
```

## Replace Rows for One Image in a Dataset Table
```python
rows = table_df[table_df["image_id"] == rec.image_id].copy()
ds.replace_rows_for_image_id("kym_velocity_events", rec.image_id, rows)
```

## Export Dataset to Legacy Folder
```python
# TIFF + JSON + CSV export
# (when artifacts/tables exist)
ds.export_legacy_folder("/tmp/exported", include_tiff=True, include_tables=True)
```

## Ingest Legacy TIFF Folder
```python
# Recursively ingests TIFFs and optional sidecars.
ds.ingest_legacy_folder("/data/legacy", pattern="*.tif", include_sidecars=True)
```
