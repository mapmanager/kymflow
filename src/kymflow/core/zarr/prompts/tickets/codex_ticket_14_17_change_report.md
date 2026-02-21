# Change Report: codex_ticket_14_17

## 1) Branch name used
- `kymflow-zarr`

## 2) Commands run and exact outcomes
- `uv run pytest src/kymflow/core/kym_dataset/tests -q`
  - Outcome: passed
  - Output: `.... [100%]`
  - Warnings:
    - `PytestConfigWarning` for unknown config options (`asyncio_mode`, `main_file`)
    - `FutureWarning` in `kymflow_zarr.dataset.replace_rows_for_image_id` (`pd.concat` with empty/all-NA entries)
- `uv run pytest src/kymflow/core/zarr/tests -q`
  - Outcome: passed
  - Output: `............................. [100%]`

## 3) Files modified (full relative paths) with per-file details

### `src/kymflow/core/kym_dataset/__init__.py`
- What changed:
  - Added package exports for `BaseIndexer` and `KymDataset`.
- Why:
  - Needed import surface for new kym dataset domain layer.
- Behavior change vs refactor-only:
  - Behavior change (new package/API exposure).

### `src/kymflow/core/kym_dataset/indexer_base.py`
- What changed:
  - Added `BaseIndexer` protocol:
    - `name: str`
    - `extract_rows(rec: ZarrImageRecord) -> pd.DataFrame`
    - `params_hash(rec: ZarrImageRecord) -> str`
    - `analysis_version() -> str`
  - Added typed signatures and Google-style docstrings.
- Why:
  - Ticket 14 required a clean extractor/indexer interface independent of dataset mutation.
- Behavior change vs refactor-only:
  - Behavior change (new public protocol contract).

### `src/kymflow/core/kym_dataset/kym_dataset.py`
- What changed:
  - Added `KymDataset` class with:
    - `__init__(self, ds: ZarrDataset)`
    - `update_index(self, indexer: BaseIndexer, *, mode: str = "replace") -> None`
  - Added internal table namespace validation:
    - indexer name must match `[a-z0-9_]+`
    - rejects reserved prefixes (`kym_`, `tables/`, `index/`)
    - table name always derived as `kym_<indexer_name>`
  - Added provenance enforcement on inserted rows:
    - `image_id`, `analysis_version`, `params_hash` are always written.
  - Implemented replace-row workflow across all image IDs using `ds.replace_rows_for_image_id`.
  - Added logging hook:
    - when previous rows for `image_id` have unchanged `params_hash`, logs TODO for future incremental mode, still replaces rows in v0.1.
- Why:
  - Tickets 15–17 required concrete domain orchestrator, namespace discipline, and provenance linking.
- Behavior change vs refactor-only:
  - Behavior change (new runtime indexing/update behavior and validations).

### `src/kymflow/core/kym_dataset/tests/test_kym_dataset_v01.py`
- What changed:
  - Added required tests:
    1. `test_indexer_row_insertion`
    2. `test_table_name_enforcement`
    3. `test_params_hash_written`
    4. `test_replace_rows_semantics`
  - Uses a small dataset fixture with temporary Zarr storage.
- Why:
  - Ticket acceptance required new kym dataset tests.
- Behavior change vs refactor-only:
  - Test-only change.

## 4) Files added
- `src/kymflow/core/kym_dataset/__init__.py`
- `src/kymflow/core/kym_dataset/indexer_base.py`
- `src/kymflow/core/kym_dataset/kym_dataset.py`
- `src/kymflow/core/kym_dataset/tests/test_kym_dataset_v01.py`
- `src/kymflow/core/zarr/prompts/codex_ticket_14_17_change_report.md`

## 5) Files deleted
- None.

## 6) Public API changes (functions/methods/signatures)
- New protocol: `kymflow.core.kym_dataset.indexer_base.BaseIndexer`
  - `name: str`
  - `extract_rows(self, rec: ZarrImageRecord) -> pd.DataFrame`
  - `params_hash(self, rec: ZarrImageRecord) -> str`
  - `analysis_version(self) -> str`
- New class: `kymflow.core.kym_dataset.kym_dataset.KymDataset`
  - `__init__(self, ds: ZarrDataset)`
  - `update_index(self, indexer: BaseIndexer, *, mode: str = "replace") -> None`

## 7) Exception handling changes
- New explicit validation exceptions in `KymDataset.update_index` path:
  - `ValueError` for unsupported mode.
  - `ValueError` for invalid/reserved indexer names.
  - `TypeError` when indexer does not return a `pd.DataFrame`.
- No broad `except Exception` introduced.

## 8) Read/write semantics changes
- `update_index` now:
  - iterates all image IDs,
  - computes per-image rows with indexer,
  - always enforces/overwrites provenance fields per row,
  - replaces rows per image in table `kym_<indexer_name>` via `replace_rows_for_image_id`.
- Existing non-kym tables are not targeted by this API and remain untouched.

## 9) Data layout changes
- Introduced kym table namespace discipline at API level:
  - writes to `tables/kym_<indexer_name>.parquet` (through existing `save_table`/`replace_rows_for_image_id` path).
- No storage layout changes inside `kymflow_zarr`.

## 10) Known limitations / TODOs
- Incremental mode is not implemented; unchanged `params_hash` currently logs a TODO and still recomputes/replaces.
- `mode` supports only `"replace"` in v0.1.
- Warning remains from `kymflow_zarr.dataset.replace_rows_for_image_id` pandas concat behavior with empty/all-NA rows (not changed in this ticket).
