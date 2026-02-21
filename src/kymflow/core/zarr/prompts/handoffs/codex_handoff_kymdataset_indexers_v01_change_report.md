# Change Report: codex_handoff_kymdataset_indexers_v01

## 1) Branch name used
- `kymflow-zarr`

## 2) Commands run and exact outcomes
- `uv run pytest src/kymflow/core/zarr/tests/test_kym_dataset_indexers.py -q`
  - First attempt (sandboxed): failed with `Operation not permitted` while accessing `/Users/cudmore/.cache/uv/sdists-v9/.git`.
  - Rerun with escalation: passed, output:
    - `.                                                                        [100%]`
- `uv run python src/kymflow/core/zarr/examples/demo_kym_dataset_v01.py`
  - Passed, output:
    - `Velocity events rows: 2`
    - `Radon report rows: 3`
    - `Updated velocity rows: 2`
    - `Rows for edited image: 1`
    - `Dataset path: /var/folders/76/6bdl7smj72g6tynz3985xxl40000gn/T/kymdataset_indexers_e24xj8h7/dataset.zarr`

## 3) Files modified (full relative paths) with what/why/behavior
- None for this ticket scope. This implementation introduced new files only; existing files were not edited as part of this specific handoff.

## 4) Files added
- `src/kymflow/core/zarr/kym_dataset.py`
- `src/kymflow/core/zarr/indexers/__init__.py`
- `src/kymflow/core/zarr/indexers/base.py`
- `src/kymflow/core/zarr/indexers/velocity_events.py`
- `src/kymflow/core/zarr/indexers/radon_report.py`
- `src/kymflow/core/zarr/tests/test_kym_dataset_indexers.py`
- `src/kymflow/core/zarr/examples/demo_kym_dataset_v01.py`

## 5) Files deleted
- None.

## 6) Public API changes (functions/methods/signatures)

### Module: `kymflow.core.zarr.kym_dataset`
Added class `KymDataset` with:
- `__init__(dataset_path: str | Path, mode: str = "a", tables: dict[str, pd.DataFrame] = ...)`
- `load_tables(names: list[str] | None = None) -> None`
- `get_table(name: str) -> pd.DataFrame`
- `save_table(name: str) -> None`
- `save_all_tables() -> None`
- `rebuild(indexer: DatasetIndexer, *, image_ids: list[str] | None = None) -> pd.DataFrame`
- `update_image(indexer: DatasetIndexer, image_id: str) -> pd.DataFrame`
- `update_images(indexer: DatasetIndexer, image_ids: list[str]) -> pd.DataFrame`

### Module: `kymflow.core.zarr.indexers.base`
Added:
- `DatasetIndexer` protocol with required members:
  - attributes: `name`, `table_name`, `schema_version`
  - methods: `extract_rows(rec: ZarrImageRecord) -> pd.DataFrame`, `required_columns() -> list[str]`
- `ensure_image_id_column(df: pd.DataFrame, image_id: str) -> pd.DataFrame`
- `normalize_table_name(name: str) -> str`

### Module: `kymflow.core.zarr.indexers.velocity_events`
Added class:
- `VelocityEventsIndexer`
  - `required_columns() -> list[str]`
  - `extract_rows(rec: ZarrImageRecord) -> pd.DataFrame`

### Module: `kymflow.core.zarr.indexers.radon_report`
Added class:
- `RadonReportIndexer`
  - `required_columns() -> list[str]`
  - `_from_payload(payload: Any) -> pd.DataFrame`
  - `extract_rows(rec: ZarrImageRecord) -> pd.DataFrame`

### Module: `kymflow.core.zarr.indexers`
Added exports via `__all__`:
- `DatasetIndexer`
- `ensure_image_id_column`
- `normalize_table_name`
- `VelocityEventsIndexer`
- `RadonReportIndexer`

## 7) Exception handling changes
- No global exception policy changes.
- New localized handling in indexers:
  - `VelocityEventsIndexer.extract_rows(...)` catches `(KeyError, RuntimeError, FileNotFoundError)` from `rec.load_df_parquet("velocity_events")`; returns empty typed DataFrame.
  - `RadonReportIndexer.extract_rows(...)` catches `(KeyError, RuntimeError, FileNotFoundError)` from parquet load, then tries JSON fallback; catches `(KeyError, FileNotFoundError)` there; returns empty typed DataFrame if both missing.
- No new exception classes were introduced.

## 8) Read/write semantics changes
- `KymDataset.rebuild(...)`:
  - Reads all targeted records through `ZarrDataset.record(image_id)`.
  - Recomputes full table and overwrites dataset-level table via `ZarrDataset.save_table(table_name, merged)`.
- `KymDataset.update_image(...)`:
  - Recomputes rows for a single image.
  - Persists via `ZarrDataset.replace_rows_for_image_id(...)`, then reloads full table from disk.
- `KymDataset.load_tables/get_table` populate in-memory cache (`self.tables`) from dataset tables.
- No storage-layer API or low-level read/write mode behavior was modified.

## 9) Data layout changes
- No new storage schema/path conventions were introduced.
- This implementation uses existing dataset-table paths indirectly through `ZarrDataset.save_table/load_table`, expected under existing table layout (`tables/<name>.parquet`).
- Newly used table names at dataset level:
  - `velocity_events`
  - `radon_report`
- Per-record artifacts consumed by indexers:
  - `velocity_events` parquet
  - `radon_report` parquet, with JSON fallback

## 10) Known limitations / TODOs
- Indexers currently normalize only column presence/order; they do not enforce value dtypes or stronger schema validation.
- `RadonReportIndexer` fallback mapping is limited to a small rename map (`vel_mean`, `vel_median`, `vel_n_valid`, `note`).
- Missing artifact handling is silent-by-design (empty rows), which may hide data pipeline issues without additional diagnostics.
- `KymDataset` keeps an in-memory cache but does not implement cache invalidation/version checks against external writers.
- Test coverage added is focused on rebuild/update happy-path and missing artifact fallback; concurrency and large-table performance are not covered.
