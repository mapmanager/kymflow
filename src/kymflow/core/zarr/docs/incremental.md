# Incremental Indexing Concepts

This page documents incremental/indexing semantics used by `kymflow.core.kym_dataset` over zarr storage.

## `params_hash`
- A deterministic hash of indexer parameters for one image.
- Stored in output table rows (`params_hash`) and run markers.
- If hash changes, prior rows are stale and should be recomputed.

## Run Marker Schema
Defined in:
- `kymflow.core.kym_dataset.run_marker`

Current schema version:
- `RUN_MARKER_VERSION = "1"`

Required fields:
- `marker_version: str`
- `indexer_name: str`
- `params_hash: str`
- `analysis_version: str`
- `n_rows: int`
- `ran_utc_epoch_ns: int`
- `status: str`

### Zero Rows Computed
A successful run that produced no rows is represented as:
- `status == "ok"`
- `n_rows == 0`

This distinguishes "computed empty" from "never computed".

## Staleness Reasons (High Level)
Typed reasons live in:
- `kymflow.core.kym_dataset.staleness.StalenessReason`

Current reasons include:
- `FRESH_ROWS`
- `FRESH_ZERO_ROWS`
- `STALE_MISSING_MARKER`
- `STALE_PARAMS_CHANGED`
- `STALE_VERSION_CHANGED`
- `STALE_MARKER_TABLE_MISMATCH`
- `STALE_UNKNOWN`

See `kymflow.core.kym_dataset.kym_dataset.KymDataset.get_staleness(...)` for how these are computed.
