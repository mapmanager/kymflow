# On-Disk Layout

The dataset is a zarr v2 directory store.

## Top-level
- `images/` record groups
- `index/manifest.json.gz` derived manifest cache
- `tables/<name>.parquet` dataset-level tables

## Per-record
For `image_id = <id>`:
- `images/<id>/data` main pixel array (authoritative)
- `images/<id>/.zattrs` record attrs (`axes`, `created_utc`, `updated_utc`, etc.)
- `images/<id>/analysis/*.json` JSON artifacts (canonical)
- `images/<id>/analysis/*.json.gz` legacy JSON fallback read path
- `images/<id>/analysis/*.parquet` tabular artifacts
- `images/<id>/analysis/*.csv.gz` optional tabular artifacts
- `images/<id>/analysis_arrays/<name>/data` N-D array artifacts

## Authoritative vs Derived
Authoritative:
- pixel arrays under `images/<id>/data`
- record artifacts under `images/<id>/analysis/*` and `analysis_arrays/*`
- dataset tables under `tables/*.parquet`

Derived/rebuildable:
- `index/manifest.json.gz`

If manifest diverges from underlying storage, regenerate with `ZarrDataset.update_manifest()`.
