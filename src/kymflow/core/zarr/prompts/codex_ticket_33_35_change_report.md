# Codex Ticket 33–35 Change Report

## 1) Branch name used
- `kymflow-zarr`

## 2) Commands run and exact outcomes
1. `uv run pytest src/kymflow/core/zarr/tests -q`
   - Outcome: `31 passed`.
2. `uv run pytest src/kymflow/core/kym_dataset/tests -q`
   - Outcome: `19 passed, 1 failed, 2 warnings`.
   - Failure:
     - `test_build_dataset_view_table_with_table_counts` expected acquired-time ordering but output ordering was not sorted by acquired timestamp.
3. `uv run pytest src/kymflow/core/zarr/tests -q` (rerun after fix)
   - Outcome: `31 passed`.
4. `uv run pytest src/kymflow/core/kym_dataset/tests -q` (rerun after fix)
   - Outcome: `20 passed, 2 warnings`.
   - Warnings (unchanged, pre-existing):
     - `PytestConfigWarning: Unknown config option: asyncio_mode`
     - `PytestConfigWarning: Unknown config option: main_file`

## 3) Files modified (full relative paths) with per-file details

### `src/kymflow/core/kym_dataset/viewer_data.py`
- What changed:
  - Replaced the previous in-function join/aggregation logic with a thin wrapper that delegates to `build_dataset_view_table(...)`.
  - Added backward-compatible parameters:
    - `include_tables: list[str] | None = None`
    - `include_velocity_events: bool | None = None`
  - Preserved prior default behavior by defaulting to `include_tables=["kym_velocity_events"]` when no explicit table list is provided.
  - Added compatibility alias column `velocity_event_count` derived from `n_rows_kym_velocity_events`.
- Why changed:
  - Ticket 35 requires reducing `build_viewer_dataframe()` to a thin wrapper over new core helpers while preserving existing call sites.
- Behavior change vs refactor-only:
  - **Behavior change** (new optional parameters, wrapper delegation, default table inclusion logic now centralized).

### `src/kymflow/core/kym_dataset/__init__.py`
- What changed:
  - Exported new public APIs: `RecordSummary`, `summarize_record`, `build_dataset_view_table`.
- Why changed:
  - Make Ticket 33/34 helpers part of core-domain import surface.
- Behavior change vs refactor-only:
  - **Behavior change** (expanded public exports).

### `src/kymflow/core/kym_dataset/tests/test_viewer_data.py`
- What changed:
  - Kept existing smoke coverage.
  - Added wrapper-equivalence test asserting `build_viewer_dataframe(...)` matches `build_dataset_view_table(...)` shape/content for velocity table count columns.
- Why changed:
  - Ticket 35 requires test coverage that `viewer_data` is now primarily a wrapper.
- Behavior change vs refactor-only:
  - **Test-only change**.

## 4) Files added

### `src/kymflow/core/kym_dataset/record_summary.py`
- Added `RecordSummary` dataclass and `summarize_record(rec: ZarrImageRecord) -> RecordSummary`.
- Implemented read-only summary extraction using:
  - manifest entry lookup if available,
  - array metadata (`shape`, `dtype`, `axes`) without pixel reads,
  - optional metadata payload/provenance payload reads.
- Missing artifacts are handled explicitly via narrow exception handling (`FileNotFoundError`, `KeyError`).

### `src/kymflow/core/kym_dataset/viewer_table.py`
- Added `build_dataset_view_table(ds: ZarrDataset, *, include_tables: list[str] | None = None) -> pd.DataFrame`.
- Produces one row per image with summary columns from `RecordSummary`.
- For each included table, performs per-image aggregation to avoid row explosion:
  - `n_rows_<table>` count by `image_id`.
- Added deterministic ordering by `acquired_local_epoch_ns` then `image_id` (missing acquisition values last).

### `src/kymflow/core/kym_dataset/tests/test_record_summary.py`
- Added tests for:
  - minimal metadata record,
  - missing metadata record,
  - ROI list counting and note extraction.

### `src/kymflow/core/kym_dataset/tests/test_viewer_table.py`
- Added tests for:
  - two-record dataset view table generation,
  - multi-row dataset-table aggregation without row explosion,
  - `n_rows_kym_velocity_events` count correctness,
  - acquired-time ordering behavior.

## 5) Files deleted
- None.

## 6) Public API changes (functions/methods/signatures)

### New module: `src/kymflow/core/kym_dataset/record_summary.py`
- `@dataclass(frozen=True) class RecordSummary`
  - Fields:
    - `image_id: str`
    - `original_path: str | None`
    - `acquired_local_epoch_ns: int | None`
    - `shape: tuple[int, ...] | None`
    - `dtype: str | None`
    - `axes: tuple[str, ...] | None`
    - `n_rois: int | None`
    - `notes: str | None`
    - `has_metadata: bool`
    - `has_rois: bool`
    - `has_header: bool`
- `summarize_record(rec: ZarrImageRecord) -> RecordSummary`

### New module: `src/kymflow/core/kym_dataset/viewer_table.py`
- `build_dataset_view_table(ds: ZarrDataset, *, include_tables: list[str] | None = None) -> pd.DataFrame`

### Updated module: `src/kymflow/core/kym_dataset/viewer_data.py`
- `build_viewer_dataframe(...)` signature changed from:
  - `build_viewer_dataframe(ds: ZarrDataset) -> pd.DataFrame`
- to:
  - `build_viewer_dataframe(ds: ZarrDataset, *, include_tables: list[str] | None = None, include_velocity_events: bool | None = None) -> pd.DataFrame`

## 7) Exception handling changes
- `summarize_record(...)` now handles expected missing-artifact cases explicitly:
  - provenance load: catches `KeyError`, `FileNotFoundError`
  - metadata payload load: catches `FileNotFoundError`
  - open array metadata read: catches `KeyError`
- No broad `except Exception` blocks introduced.

## 8) Read/write semantics changes
- New helpers are read-only:
  - no calls to write APIs,
  - no group creation APIs,
  - no pixel array materialization (`load_array`) used.
- Viewer table now derives per-image row counts from selected dataset tables and returns one row per image by design.

## 9) Data layout changes
- None.
- No storage schema/path changes to Zarr groups, artifacts, dataset tables, or manifest keys.

## 10) Known limitations / TODOs
- `summarize_record(...)` currently performs a manifest lookup by scanning manifest image entries per record call; for very large datasets, caching/lookup indexing may be added later for lower overhead.
- Table aggregation in `build_dataset_view_table(...)` is intentionally minimal (`n_rows_<table>` only). Additional aggregate metrics (e.g., numeric min/max/mean) are not implemented in this ticket.
- Existing pytest configuration warnings remain out of scope (`asyncio_mode`, `main_file`).
