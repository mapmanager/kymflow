# Change Report: codex_ticket_22_25

## 1) Branch name used
- `kymflow-zarr`

## 2) Commands run and exact outcomes
- `uv run pytest src/kymflow/core/kym_dataset/tests -q`
  - Outcome: passed (`9 passed`)
  - Warnings:
    - `PytestConfigWarning` unknown config options (`asyncio_mode`, `main_file`)
    - `FutureWarning` from `kymflow_zarr.dataset.replace_rows_for_image_id` pandas concat behavior
- `uv run pytest src/kymflow/core/zarr/tests -q`
  - Outcome: passed (`............................. [100%]`)
- `uv run python src/kymflow/core/zarr/examples/demo_kymdataset_velocity_events_empty_v01.py`
  - Initial sandbox run failed with uv cache permission error (`Operation not permitted` on `/Users/cudmore/.cache/uv/sdists-v9/.git`)
  - First escalated attempt was rejected
  - Second escalated attempt passed, output:
    - `replace stats: {'updated': 1, 'skipped': 0, 'missing': 1}`
    - `incremental stats (marker-matched): {'updated': 0, 'skipped': 1, 'missing': 1}`
    - `incremental stats (params changed): {'updated': 1, 'skipped': 0, 'missing': 1}`
- `uv run python src/kymflow/core/zarr/examples/demo_kymdataset_radon_roi_staleness_v01.py`
  - Initial sandbox run failed with uv cache permission error
  - Escalated rerun passed, output:
    - `replace stats: {'updated': 1, 'skipped': 0, 'missing': 1}`
    - `incremental stats (no ROI change): {'updated': 0, 'skipped': 1, 'missing': 0}`
    - `incremental stats (ROI edited): {'updated': 1, 'skipped': 0, 'missing': 0}`

## 3) Files modified (full relative paths) with per-file details

### `src/kymflow/core/kym_dataset/indexer_base.py`
- What changed:
  - Added optional protocol hook:
    - `load_run_marker(self, rec: ZarrImageRecord) -> dict[str, object] | None`
    - default implementation returns `None`.
- Why:
  - Ticket 22 requires generic computed-marker support for zero-row analyses.
- Behavior change vs refactor-only:
  - API behavior changed (new optional indexer hook available).

### `src/kymflow/core/kym_dataset/kym_dataset.py`
- What changed:
  - Enhanced incremental logic in `update_index`:
    - when existing rows for `image_id` are absent, checks `indexer.load_run_marker(rec)` (if implemented),
    - if marker `params_hash` + `analysis_version` match current values, skips recompute.
  - Existing row-based skip behavior unchanged for non-empty per-image rows.
- Why:
  - Ticket 22 requires incremental correctness for valid zero-row results.
- Behavior change vs refactor-only:
  - Behavior changed (incremental mode can now skip missing-row images using marker).

### `src/kymflow/core/kym_dataset/indexers/velocity_events.py`
- What changed:
  - Added canonical constants:
    - params key `velocity_events/params`
    - events key `velocity_events/events`
    - marker key `velocity_events/summary`
  - Added `load_run_marker(rec)` reading summary JSON.
  - Added `write_run_marker(rec, *, params_hash, analysis_version, n_events)` helper.
  - Ensured `extract_rows(rec)` returns stable schema even when empty (event columns always present).
  - Kept params hash via deterministic helper and retained parquet/csv fallbacks for events artifact loading.
- Why:
  - Ticket 23 requires marker read/write and empty-result stability.
- Behavior change vs refactor-only:
  - Behavior changed (marker support + stable empty schema output).

### `src/kymflow/core/kym_dataset/indexers/__init__.py`
- What changed:
  - Added export for `RadonIndexer`.
- Why:
  - Ticket 24 introduces second real indexer.
- Behavior change vs refactor-only:
  - API export changed.

### `src/kymflow/core/kym_dataset/__init__.py`
- What changed:
  - Added exports for `VelocityEventIndexer` and `RadonIndexer`.
- Why:
  - Surface new domain indexers from package root.
- Behavior change vs refactor-only:
  - API export changed.

### `src/kymflow/core/kym_dataset/tests/test_velocity_event_indexer.py`
- What changed:
  - Added test `test_velocity_events_zero_rows_uses_run_marker_for_incremental_skip`.
  - Validates:
    - zero-row replace run persists as computed via marker,
    - incremental skip occurs when marker matches,
    - params change invalidates marker and recomputes.
- Why:
  - Ticket 22/23 acceptance tests.
- Behavior change vs refactor-only:
  - Test-only change.

## 4) Files added
- `src/kymflow/core/kym_dataset/indexers/radon.py`
- `src/kymflow/core/kym_dataset/tests/test_radon_indexer.py`
- `src/kymflow/core/zarr/examples/demo_kymdataset_velocity_events_empty_v01.py`
- `src/kymflow/core/zarr/examples/demo_kymdataset_radon_roi_staleness_v01.py`
- `src/kymflow/core/zarr/prompts/codex_ticket_22_25_change_report.md`

## 5) Files deleted
- None.

## 6) Public API changes (functions/methods/signatures)

### `kymflow.core.kym_dataset.indexer_base.BaseIndexer`
- Added optional hook:
  - `load_run_marker(self, rec: ZarrImageRecord) -> dict[str, object] | None`

### `kymflow.core.kym_dataset.indexers.velocity_events.VelocityEventIndexer`
- Added methods:
  - `load_run_marker(self, rec: ZarrImageRecord) -> dict[str, object] | None`
  - `write_run_marker(rec: ZarrImageRecord, *, params_hash: str, analysis_version: str, n_events: int) -> None`

### `kymflow.core.kym_dataset.indexers.radon.RadonIndexer` (new class)
- Added:
  - `name = "radon"`
  - `analysis_version(self) -> str`
  - `params_hash(self, rec: ZarrImageRecord) -> str` (includes ROI envelopes)
  - `extract_rows(self, rec: ZarrImageRecord) -> pd.DataFrame`

## 7) Exception handling changes
- No broad `except Exception` introduced.
- New/updated targeted handling:
  - `VelocityEventIndexer.load_run_marker`: catches `(KeyError, FileNotFoundError)` when summary missing.
  - `VelocityEventIndexer` artifact loads continue to use targeted key/file/runtime exceptions.
  - `RadonIndexer` loads use targeted `(KeyError, FileNotFoundError, RuntimeError)` fallback logic.

## 8) Read/write semantics changes
- Incremental update semantics changed in `KymDataset`:
  - `no existing rows` no longer implies recompute; marker match can skip.
- Velocity events marker semantics:
  - marker artifact `velocity_events/summary` can represent “analysis computed with 0 events.”
  - This prevents perpetual recompute on empty event outputs.
- Radon indexer params hash semantics:
  - hash now incorporates ROI envelopes loaded from metadata payload.
  - ROI geometry edits change hash and trigger incremental recompute.

## 9) Data layout changes
- Added marker artifact convention for velocity events:
  - `images/<image_id>/analysis/velocity_events/summary.json`
  - fields used: `analysis_version`, `params_hash`, `n_events` (plus optional future timestamp fields)
- Added radon indexer artifact read conventions (domain-side only; storage layer unchanged):
  - params: `radon/params`
  - results: `radon/results` (with fallback names)
- No storage-layer (`kymflow_zarr`) schema changes.

## 10) Known limitations / TODOs
- Marker-based skip is only used when per-image table rows are absent; if rows exist, row-based provenance comparison remains the decision path.
- `missing` counter in stats still increments for marker-skipped zero-row records (reflects no existing table rows, not failure).
- Radon marker support is not implemented (ticket did not require it); radon incremental skip relies on existing rows + provenance columns.
- Existing pandas concat `FutureWarning` remains in `kymflow_zarr.dataset.replace_rows_for_image_id` (out of scope here).
