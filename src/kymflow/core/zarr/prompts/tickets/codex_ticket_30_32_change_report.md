# Codex Ticket 30–32 Change Report

## 1) Branch name used
- `kymflow-zarr`

## 2) Commands run and exact outcomes
1. `uv run pytest src/kymflow/core/zarr/tests -q`
   - Outcome: `31 passed` (no failures).
2. `uv run pytest src/kymflow/core/kym_dataset/tests -q`
   - Outcome: `15 passed, 2 warnings`.
   - Warnings:
     - `PytestConfigWarning: Unknown config option: asyncio_mode`
     - `PytestConfigWarning: Unknown config option: main_file`

## 3) Files modified (full relative paths) with per-file details

### `src/kymflow/core/kym_dataset/kym_dataset.py`
- What changed:
  - Replaced `last_update_stats` schema from `{updated, skipped, missing}` to explicit counters:
    - `updated`, `skipped_fresh`, `skipped_zero_rows`, `stale_missing_marker`, `stale_marker_table_mismatch`, `total_images`.
  - `get_staleness(...)` now returns typed `StalenessResult` instead of `dict`.
  - Added staleness reason mapping to `StalenessReason` enum values.
  - Added run-marker read/write integration using centralized helpers (`make_run_marker`, `validate_run_marker`, `marker_matches`, `marker_n_rows`).
  - `update_index(...)` incremental path now increments explicit counters by staleness reason.
  - Log summary line changed to include all explicit counters.
  - Local in-memory table snapshot update now avoids concat when normalized rows are empty.
- Why changed:
  - Implement Ticket 30 explicit stats, Ticket 31 typed staleness, and Ticket 32 run-marker contract + warning cleanup.
- Behavior vs refactor:
  - **Behavior changed** (stats shape, staleness return type/logic, marker handling, incremental accounting semantics).

### `src/kymflow/core/kym_dataset/indexers/velocity_events.py`
- What changed:
  - Switched logger initialization to `get_logger`.
  - `load_run_marker(...)` now validates markers via shared run-marker contract and supports legacy marker conversion (`n_events`/`computed_utc_epoch_ns` -> contract form).
  - `write_run_marker(...)` now writes contract-compliant marker via `make_run_marker(...)` and uses `n_rows` argument.
- Why changed:
  - Ticket 32 requires centralized run-marker schema and shared helper usage in indexers (VelocityEventIndexer minimum).
- Behavior vs refactor:
  - **Behavior changed** (marker payload schema and validation behavior).

### `src/kymflow/core/zarr/src/kymflow_zarr/dataset.py`
- What changed:
  - `replace_rows_for_image_id(...)` now uses three branches:
    - existing empty -> write `df_rows` directly,
    - `df_rows` empty -> write filtered existing directly,
    - both non-empty -> concat.
- Why changed:
  - Ticket 32 requires eliminating pandas concat FutureWarning path with empty/all-NA concat cases.
- Behavior vs refactor:
  - **Behavior changed** only in edge-case write path selection (result table semantics unchanged by design).

### `src/kymflow/core/kym_dataset/tests/test_velocity_event_indexer.py`
- What changed:
  - Updated assertions to explicit stats keys.
  - Updated staleness assertions to typed `StalenessResult` and `StalenessReason` enums.
  - Updated marker writer calls to `n_rows`.
  - Added assertions that stale counters increment for:
    - missing marker,
    - marker/table mismatch,
    - zero-row fresh skip,
    - normal fresh-row skip.
- Why changed:
  - Validate Ticket 30 and 31 semantics.
- Behavior vs refactor:
  - **Test-only change**.

### `src/kymflow/core/kym_dataset/tests/test_kym_dataset_v01.py`
- What changed:
  - Updated log assertion to new summary keys (`skipped_fresh`, `skipped_zero_rows`).
- Why changed:
  - Log format changed with explicit counters (Ticket 30).
- Behavior vs refactor:
  - **Test-only change**.

### `src/kymflow/core/kym_dataset/tests/test_radon_indexer.py`
- What changed:
  - Updated assertions from `skipped` to `skipped_fresh`.
- Why changed:
  - Stats schema changed (Ticket 30).
- Behavior vs refactor:
  - **Test-only change**.

### `src/kymflow/core/zarr/tests/test_dataset_tables.py`
- What changed:
  - Added coverage for replace_rows edge cases:
    - existing empty + new non-empty,
    - existing non-empty + new empty (removal path),
    - existing non-empty + new non-empty (existing test retained).
- Why changed:
  - Validate Ticket 32 replace_rows warning fix and branch semantics.
- Behavior vs refactor:
  - **Test-only change**.

## 4) Files added
- `src/kymflow/core/kym_dataset/staleness.py`
  - Adds `StalenessReason` enum and immutable `StalenessResult` dataclass.
- `src/kymflow/core/kym_dataset/run_marker.py`
  - Adds `RUN_MARKER_VERSION = "1"` and helpers:
    - `make_run_marker(...)`
    - `validate_run_marker(...)`
    - `marker_matches(...)`
    - `marker_n_rows(...)`
- `src/kymflow/core/kym_dataset/tests/test_run_marker.py`
  - Adds tests for marker creation, validation, matching, and invalid value handling.

## 5) Files deleted
- None.

## 6) Public API changes (functions/methods/signatures)

### `src/kymflow/core/kym_dataset/kym_dataset.py`
- `KymDataset.get_staleness(...)`
  - **Before:** returned `dict[str, object]`.
  - **After:** returns `StalenessResult`.
- `KymDataset.last_update_stats`
  - **Before keys:** `updated`, `skipped`, `missing`.
  - **After keys:** `updated`, `skipped_fresh`, `skipped_zero_rows`, `stale_missing_marker`, `stale_marker_table_mismatch`, `total_images`.

### `src/kymflow/core/kym_dataset/indexers/velocity_events.py`
- `VelocityEventIndexer.write_run_marker(...)`
  - **Before:** `(..., n_events: int)` (legacy payload).
  - **After:** `(..., n_rows: int)` (contract payload).

### `src/kymflow/core/kym_dataset/run_marker.py` (new module)
- New public helpers:
  - `make_run_marker(...) -> dict[str, object]`
  - `validate_run_marker(...) -> None`
  - `marker_matches(...) -> bool`
  - `marker_n_rows(...) -> int | None`
- New public constant:
  - `RUN_MARKER_VERSION: str = "1"`

### `src/kymflow/core/kym_dataset/staleness.py` (new module)
- New public enum:
  - `StalenessReason`
- New public dataclass:
  - `StalenessResult`

## 7) Exception handling changes
- `VelocityEventIndexer.load_run_marker(...)`:
  - now returns `None` for invalid marker payloads after validation failure and logs warning.
- `KymDataset._load_standard_run_marker(...)`:
  - now validates payload and returns `None` on invalid schema.
- `run_marker.validate_run_marker(...)`:
  - raises `ValueError` with field-specific messages for missing/invalid marker fields.

## 8) Read/write semantics changes
- Incremental index updates now classify skip/stale conditions via typed staleness reasons and update explicit counters.
- Per-image run markers are written in centralized schema form (`marker_version`, `n_rows`, `ran_utc_epoch_ns`, etc.).
- `replace_rows_for_image_id(...)` now avoids concat for empty-input branches and writes direct DataFrames in those branches.

## 9) Data layout changes
- Marker storage path for velocity remains unchanged (`images/<image_id>/analysis/velocity_events/summary.json.gz`), but payload schema changed to contract format:
  - Added required keys: `marker_version`, `indexer_name`, `n_rows`, `ran_utc_epoch_ns`, `status`.
  - Legacy marker payloads (`n_events`, `computed_utc_epoch_ns`) are converted on load in `VelocityEventIndexer`.
- No changes to table paths (`tables/*.parquet`) or manifest layout.

## 10) Known limitations / TODOs
- Marker contract migration is implemented for `VelocityEventIndexer` and KymDataset standard marker helpers; other indexers can migrate to explicit shared marker helpers for uniformity.
- Existing unrelated pytest config warnings (`asyncio_mode`, `main_file`) remain and are not part of this ticket scope.
