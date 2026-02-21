# Kymflow Zarr Core Docs

This folder documents the **zarr core API contract** for:
- `kymflow_zarr` storage APIs (`ZarrDataset`, `ZarrImageRecord`)
- dataset/record layout and workflows
- incremental-index context used by `kym_dataset`

## Definitions
- **Dataset**: a zarr root containing image records, dataset tables, and index artifacts.
- **Record**: one image entry under `images/<image_id>/` with pixels and analysis artifacts.
- **Manifest**: `index/manifest.json.gz`; derived cache/index for ordering and quick listing.
- **Artifacts**: per-record analysis blobs under `images/<image_id>/analysis/*` and `analysis_arrays/*`.
- **Tables**: dataset-level Parquet tables under `tables/<name>.parquet`.
- **Run marker**: per-record JSON marker used by incremental indexers (defined in `kymflow.core.kym_dataset.run_marker`).

## Contract Rule
These docs are a living contract. If a change affects any public API surface, method signature, read/write semantics, on-disk layout, ingest/export flow, or caller-visible exceptions, update docs in the same ticket/PR.

Primary contract pages:
- `api.md`
- `layout.md`
- `workflows.md`
- `incremental.md`
