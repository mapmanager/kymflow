# Change Report: codex_ticket_26_29

## 1) Branch name used
- `kymflow-zarr`

## 2) Commands run and exact outcomes
- `uv run pytest src/kymflow/core/kym_dataset/tests -q`
  - Outcome: passed (`12 passed`)
  - Warnings:
    - `PytestConfigWarning` for unknown options (`asyncio_mode`, `main_file`)
    - `FutureWarning` from pandas concat behavior in:
      - `src/kymflow/core/zarr/src/kymflow_zarr/dataset.py`
      - `src/kymflow/core/kym_dataset/kym_dataset.py`
- `uv run pytest src/kymflow/core/zarr/tests -q`
  - Outcome: passed (`............................. [100%]`)
- Pipeline idempotence run:
  - Command:
    - create temp TIFF
    - run `uv run python src/kymflow/core/zarr/examples/demo_pipeline_cli_v01.py --input <tmp>/input --dataset <tmp>/dataset.zarr --ingest-new-only` twice
  - Outcome:
    - First run: `scanned=1 ingested=1`
    - Second run: `scanned=1 ingested=0`
    - Both runs completed with manifest and indexer summaries.
- Viewer smoke run:
  - Command:
    - create temp dataset with one image
    - run `uv run python src/kymflow/core/zarr/examples/demo_nicegui_viewer_v01.py --dataset <tmp>/dataset.zarr --smoke`
  - Outcome:
    - `rows: 1`
    - `columns: ['image_id', 'original_path', 'acquired_local_epoch_ns']`

## 3) Files modified (full relative paths) with per-file details

### `src/kymflow/core/kym_dataset/kym_dataset.py`
- What changed:
  - Added standard run marker load/write helpers:
    - `_load_standard_run_marker(...)`
    - `_write_standard_run_marker(...)`
  - Added public staleness API:
    - `get_staleness(table_name, image_id, params_hash, *, analysis_version, indexer=None, rec=None) -> dict[str, object]`
  - Extended incremental algorithm in `update_index(...)`:
    - uses staleness object (`has_run_marker`, `table_rows_present`, `params_hash_matches`, `is_stale`, `reason`)
    - supports marker-driven skip for true 0-row outcomes
    - treats marker/table mismatch (`n_rows=0` marker but table rows present) as stale/rebuild
  - Writes standard marker on each successful update under `analysis/<indexer_name>_run.json`.
- Why:
  - Ticket 26 incremental hardening and explicit staleness diagnostics.
- Behavior change vs refactor-only:
  - Behavior changed (incremental correctness and staleness semantics changed).

### `src/kymflow/core/kym_dataset/indexers/velocity_events.py`
- What changed:
  - Added canonical marker/params/events keys constants.
  - Added `load_run_marker(rec)` reading `velocity_events/summary`.
  - Added `write_run_marker(rec, *, params_hash, analysis_version, n_events)`; now writes `computed_utc_epoch_ns`.
  - Ensured `extract_rows(...)` returns stable schema even when no events are present.
  - Normalized output column ordering.
- Why:
  - Ticket 23 requirements for zero-result marker support and stable empty results.
- Behavior change vs refactor-only:
  - Behavior changed (run marker support and empty output behavior).

### `src/kymflow/core/kym_dataset/__init__.py`
- What changed:
  - Added export for `build_viewer_dataframe`.
- Why:
  - Expose viewer dataframe helper for demos/consumers.
- Behavior change vs refactor-only:
  - API export change.

### `src/kymflow/core/kym_dataset/tests/test_velocity_event_indexer.py`
- What changed:
  - Added/extended assertions for:
    - 0-row marker skip correctness
    - stale reason `marker_zero_rows_fresh`
    - stale reason `missing_marker`
    - mismatch reason `marker_table_mismatch`
    - rerun path that removes previously existing rows when new result is empty.
- Why:
  - Ticket 26/23 test requirements.
- Behavior change vs refactor-only:
  - Test-only change.

## 4) Files added
- `src/kymflow/core/kym_dataset/viewer_data.py`
- `src/kymflow/core/kym_dataset/tests/test_viewer_data.py`
- `src/kymflow/core/zarr/examples/demo_pipeline_cli_v01.py`
- `src/kymflow/core/zarr/examples/demo_nicegui_viewer_v01.py`
- `src/kymflow/core/zarr/prompts/codex_ticket_26_29_change_report.md`

## 5) Files deleted
- None.

## 6) Public API changes (functions/methods/signatures)

### `src/kymflow/core/kym_dataset/kym_dataset.py`
- Added:
  - `get_staleness(self, table_name: str, image_id: str, params_hash: str, *, analysis_version: str, indexer: BaseIndexer | None = None, rec: Any | None = None) -> dict[str, object]`
- Existing:
  - `update_index(...)` behavior extended (signature unchanged from prior ticket: `Literal["replace", "incremental"]`).

### `src/kymflow/core/kym_dataset/indexers/velocity_events.py`
- Added:
  - `load_run_marker(self, rec: ZarrImageRecord) -> dict[str, object] | None`
  - `write_run_marker(rec: ZarrImageRecord, *, params_hash: str, analysis_version: str, n_events: int) -> None`

### `src/kymflow/core/kym_dataset/viewer_data.py`
- Added:
  - `build_viewer_dataframe(ds: ZarrDataset) -> pd.DataFrame`

### `src/kymflow/core/zarr/examples/demo_nicegui_viewer_v01.py`
- Added pure function:
  - `plot_heatmap_dict(arr: np.ndarray, *, title: str = "") -> dict`

## 7) Exception handling changes
- `KymDataset` staleness marker loading uses targeted missing-artifact handling through existing record APIs.
- No new broad `except Exception` blocks introduced.
- Pipeline CLI uses targeted `ImportError` handling for tifffile requirement.

## 8) Read/write semantics changes
- `KymDataset.update_index(...)` now writes run markers on update:
  - `analysis/<indexer_name>_run.json`
  - payload includes `indexer_name`, `params_hash`, `analysis_version`, `ran_utc_epoch_ns`, `status`, `n_rows`.
- Incremental mode semantics:
  - if table rows absent but marker matches and marker indicates zero rows, image is skippable (not stale).
  - marker/table inconsistency triggers rebuild.
- Velocity event summary marker (`velocity_events/summary`) remains supported and used via indexer hook.

## 9) Data layout changes
- Added standard per-record run marker artifact convention:
  - `images/<image_id>/analysis/<indexer_name>_run.json`
- No change to storage-layer JSON write policy:
  - new JSON artifacts continue to write `.json`
  - legacy `.json.gz` reads remain available through existing `load_json` fallback.
- Pipeline CLI provenance fields written on ingest:
  - `original_path`, `file_size`, `mtime_ns` (in `analysis/provenance.json`).

## 10) Known limitations / TODOs
- `demo_nicegui_viewer_v01.py` was validated in `--smoke` mode (data path); full interactive launch is environment-dependent and not exercised in automated test runs.
- `get_staleness(...)` currently returns a dict (not a typed dataclass).
- `missing` count in update stats still tracks absence of table rows before decision; it can be non-zero even when marker-based skip occurs.
- Existing pandas concat `FutureWarning` remains in dataset/table merge logic (out of scope for this ticket).
