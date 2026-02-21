# Codex Ticket 36–38 Change Report

## 1) Branch name used
- `kymflow-zarr`

## 2) Commands run and exact outcomes
1. `uv run pytest src/kymflow/core/zarr/tests -q`
   - Outcome: `33 passed`.

## 3) Files modified (full relative paths) with per-file details

### `src/kymflow/core/zarr/prompts/codex_run_ticket.md`
- What changed:
  - Strengthened docs contract rule by adding: if docs are required and not updated, ticket is incomplete.
  - Clarified final checklist line to require explicit docs status and justification if not required.
- Why changed:
  - Ticket 38 requirement to enforce docs updates in workflow prompt.
- Behavior change vs refactor-only:
  - **Behavior change** in workflow instructions (agent execution policy), no runtime code path impact.

### `src/kymflow/core/zarr/prompts/codex_implement_ticket_and_gen_report_prompt.md`
- What changed:
  - Added docs-update rule for API/semantics/layout/exception changes under `src/kymflow/core/zarr/docs/`.
  - Added final response checklist line: docs updated yes/no with files.
- Why changed:
  - Ticket 38 requirement for same docs policy in implement+report template.
- Behavior change vs refactor-only:
  - **Behavior change** in workflow instructions (agent execution policy), no runtime code path impact.

## 4) Files added

### `src/kymflow/core/zarr/docs/README.md`
- Added docs suite entrypoint with scope definitions (Dataset/Record/Manifest/Artifacts/Tables/Run marker) and explicit “docs must update with API changes” rule.

### `src/kymflow/core/zarr/docs/api.md`
- Added API contract page enumerating intended public surfaces and signatures for:
  - `kymflow_zarr.ZarrDataset`
  - `kymflow_zarr.ZarrImageRecord`
  - `kymflow_zarr.MetadataNotFoundError`
  - `kymflow.core.kym_dataset.run_marker` helpers
- Includes read/write semantics and caller-visible exception notes.

### `src/kymflow/core/zarr/docs/layout.md`
- Added on-disk layout contract for:
  - `images/<id>/data`
  - `images/<id>/analysis/*`
  - `images/<id>/analysis_arrays/*`
  - `index/manifest.json.gz`
  - `tables/<name>.parquet`
- Explicitly labels authoritative vs derived data.

### `src/kymflow/core/zarr/docs/workflows.md`
- Added runnable workflow snippets for:
  - create/open dataset
  - Ingest TIFF (`tifffile.imread + add_image`)
  - provenance JSON attach
  - canonical metadata payload/object flows
  - per-record and dataset table read/write
  - export/import legacy folder APIs

### `src/kymflow/core/zarr/docs/incremental.md`
- Added incremental-index reference:
  - `params_hash` meaning
  - run-marker schema v1 and zero-row representation
  - staleness reason list and pointer to `kym_dataset` typed staleness

### `src/kymflow/core/zarr/tests/test_docs_contract_smoke.py`
- Added smoke test that:
  - verifies required docs files exist,
  - checks `api.md` includes `ZarrDataset` and `ZarrImageRecord`,
  - checks `workflows.md` includes `Ingest TIFF`.

## 5) Files deleted
- None.

## 6) Public API changes (functions/methods/signatures)
- No runtime Python public API changes in `kymflow_zarr` or `kym_dataset` code.
- Added documentation-only contract pages and workflow-prompt policy changes.

## 7) Exception handling changes
- No code exception behavior changes.
- Documentation now explicitly records exception semantics for key APIs (e.g., `FileNotFoundError`, `ValueError`, `PermissionError`, `MetadataNotFoundError`).

## 8) Read/write semantics changes
- No runtime read/write behavior changes.
- Added explicit read/write semantics documentation for existing APIs.

## 9) Data layout changes
- No on-disk data layout changes.
- Added formal layout documentation in `docs/layout.md` for existing paths.

## 10) Known limitations / TODOs
- Docs smoke test is intentionally minimal string-presence validation; it does not validate signature drift automatically.
- `docs/api.md` is manually maintained; a future improvement is generating API signature sections from source introspection.
