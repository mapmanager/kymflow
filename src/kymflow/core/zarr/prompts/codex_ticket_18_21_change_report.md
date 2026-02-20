# Change Report: codex_ticket_18_21

## 1) Branch name used
- `kymflow-zarr`

## 2) Commands run and exact outcomes
- `uv run pytest src/kymflow/core/kym_dataset/tests -q`
  - Outcome: passed (`7 passed`)
  - Warnings:
    - `PytestConfigWarning` for unknown config options (`asyncio_mode`, `main_file`)
    - `FutureWarning` from `kymflow_zarr.dataset.replace_rows_for_image_id` concat behavior.
- `uv run pytest src/kymflow/core/zarr/tests -q`
  - Outcome: passed (`............................. [100%]`)
- `uv run python src/kymflow/core/zarr/examples/demo_kymdataset_velocity_events_v01.py`
  - First run in sandbox failed due uv cache permission (`Operation not permitted` on `/Users/cudmore/.cache/uv/sdists-v9/.git`)
  - Rerun with escalation: passed
  - Output included:
    - `replace stats: {'updated': 2, 'skipped': 0, 'missing': 2}`
    - `incremental stats (no changes): {'updated': 0, 'skipped': 2, 'missing': 0}`
    - `incremental stats (one params changed): {'updated': 1, 'skipped': 1, 'missing': 0}`
    - `rows: 2`
    - `table key exists: True`

## 3) Files modified (full relative paths) with per-file details

### `src/kymflow/core/kym_dataset/__init__.py`
- What changed:
  - Added exports for provenance helpers: `stable_json_dumps`, `params_hash`.
- Why:
  - Ticket 18 requires canonical params hashing utility API.
- Behavior change vs refactor-only:
  - Behavior change (new public exports).

### `src/kymflow/core/kym_dataset/kym_dataset.py`
- What changed:
  - Updated `update_index` signature to:
    - `mode: Literal["replace", "incremental"] = "replace"`.
  - Implemented incremental staleness logic by comparing existing per-image rows:
    - skip when `params_hash` and `analysis_version` both unchanged.
  - Added summary counters and logging (`updated`, `skipped`, `missing`).
  - Added `last_update_stats` dict on class instance for run summary visibility.
- Why:
  - Ticket 19 requires incremental mode and staleness checks.
- Behavior change vs refactor-only:
  - Behavior change (new incremental skip path, updated logging/stats semantics).

### `src/kymflow/core/kym_dataset/tests/test_kym_dataset_v01.py`
- What changed:
  - Updated replace semantics test to validate incremental skip behavior and summary logging (`updated=0 skipped=3 missing=0`).
- Why:
  - Align existing tests with new incremental mode behavior from Ticket 19.
- Behavior change vs refactor-only:
  - Test-only change.

## 4) Files added
- `src/kymflow/core/kym_dataset/provenance.py`
- `src/kymflow/core/kym_dataset/indexers/__init__.py`
- `src/kymflow/core/kym_dataset/indexers/velocity_events.py`
- `src/kymflow/core/kym_dataset/tests/test_provenance.py`
- `src/kymflow/core/kym_dataset/tests/test_velocity_event_indexer.py`
- `src/kymflow/core/zarr/examples/demo_kymdataset_velocity_events_v01.py`
- `src/kymflow/core/zarr/prompts/codex_ticket_18_21_change_report.md`

## 5) Files deleted
- None.

## 6) Public API changes (functions/methods/signatures)

### `src/kymflow/core/kym_dataset/provenance.py`
- Added:
  - `stable_json_dumps(obj: object) -> str`
  - `params_hash(params: dict[str, Any]) -> str`

### `src/kymflow/core/kym_dataset/kym_dataset.py`
- Updated:
  - `update_index(self, indexer: BaseIndexer, *, mode: Literal["replace", "incremental"] = "replace") -> None`

### `src/kymflow/core/kym_dataset/indexers/velocity_events.py`
- Added:
  - `class VelocityEventIndexer(BaseIndexer)`
    - `name = "velocity_events"`
    - `analysis_version(self) -> str`
    - `params_hash(self, rec: ZarrImageRecord) -> str`
    - `extract_rows(self, rec: ZarrImageRecord) -> pd.DataFrame`

### `src/kymflow/core/kym_dataset/indexers/__init__.py`
- Added public export:
  - `VelocityEventIndexer`

## 7) Exception handling changes
- `VelocityEventIndexer` uses targeted fallback handling:
  - For params JSON load: catches `(KeyError, FileNotFoundError)` and falls back to defaults.
  - For events table load: catches `(KeyError, FileNotFoundError, RuntimeError)` for parquet and `(KeyError, FileNotFoundError)` for CSV fallback.
- `KymDataset.update_index` now raises:
  - `ValueError` for invalid mode values outside `{"replace","incremental"}`.
- No broad `except Exception` introduced.

## 8) Read/write semantics changes
- Replace mode:
  - unchanged core behavior (recompute and replace per image).
- Incremental mode:
  - reads existing table once,
  - evaluates per-image staleness using `params_hash` + `analysis_version`,
  - skips row replacement when unchanged,
  - replaces only stale/missing rows.
- `VelocityEventIndexer` reads record-level artifacts:
  - params: `velocity_events/params` (with fallbacks),
  - events table: `velocity_events/events` parquet/csv.gz (with fallback to `velocity_events` name).

## 9) Data layout changes
- No storage-layer schema/path changes in `kymflow_zarr`.
- Expected per-record artifact usage by `VelocityEventIndexer`:
  - params JSON: `images/<id>/analysis/velocity_events/params.json` (via `save_json("velocity_events/params", ...)`)
  - events table: `images/<id>/analysis/velocity_events/events.parquet` (via `save_df_parquet("velocity_events/events", ...)`)
- Dataset-level index table written by `KymDataset`:
  - `tables/kym_velocity_events.parquet`

## 10) Known limitations / TODOs
- Incremental staleness decision currently uses only `params_hash` + `analysis_version`; it does not detect pixel/source-file content changes.
- `KymDataset.update_index` still supports only `replace` and `incremental` (no additional modes).
- Existing pandas concat FutureWarning in storage layer remains unresolved (outside this ticket scope).
