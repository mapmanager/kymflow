# New Ticket Set — KymDataset + Indexers v0.1 (Codex-ready)

This set builds the dataset-level orchestration layer that replicates the core behavior of `KymImageList` caches:
- dataset-level summary tables derived from per-image artifacts
- easy incremental updates when one image changes
- easy full rebuild

It assumes Tickets 3–6 will land soon, but KymDataset can be built either before or after them.

---

## Where should KymDataset live? (Decision + guidance)

### Option 1 — `kymflow.core` (recommended)
Put KymDataset in `kymflow` (domain layer), importing `kymflow_zarr` storage.

**Pros**
- Correct layering: storage stays generic; orchestration stays domain-specific.
- Easier to evolve analysis conventions without touching storage primitives.
- Lets other datasets reuse storage without inheriting kym-specific opinions.

**Cons**
- Slightly more project surface area (new module in core).

### Option 2 — inside `kymflow_zarr` (acceptable early, but less clean)
Put KymDataset inside the storage subpackage as a “first example orchestrator”.

**Pros**
- Everything is in one place for early development.
- Fast iteration while you’re still exploring.

**Cons**
- Risk of drifting kymflow-specific semantics into the storage layer.
- Harder later to extract storage or support other modalities.

**Implementation target for v0.1**: choose Option 1.

This ticket set assumes Option 1:
- `src/kymflow/core/zarr/kym_dataset.py`
- `src/kymflow/core/zarr/indexers/**`

---

## Shared conventions (v0.1)

Per-image artifacts (inside record `analysis/`):
- JSON dict: `<name>.json` (Ticket 5 makes this canonical)
- Table: `<name>.parquet`

Dataset tables (at dataset root):
- `tables/<name>.parquet`

**Required column**
Every dataset-level table must include:
- `image_id` (str uuid)

---

## Ticket KD1 — Add Indexer Protocol + base utilities

### Goal
Define a minimal interface for “derived dataset tables”.

### Add file
- `src/kymflow/core/zarr/indexers/base.py`

Define:
- `class DatasetIndexer(Protocol):`
  - `name: str`
  - `table_name: str`
  - `schema_version: str` (optional but recommended)
  - `def extract_rows(self, rec: "ZarrImageRecord") -> pd.DataFrame: ...`
  - `def required_columns(self) -> list[str]: ...` (optional; default empty)

Also add:
- helper `ensure_image_id_column(df, image_id)`
- helper `normalize_table_name(name)` (lowercase, safe chars)

### Acceptance
- MyPy-friendly typing (use TYPE_CHECKING to avoid runtime imports)
- Unit test verifying protocol-style usage (optional)

---

## Ticket KD2 — Implement `KymDataset` orchestrator (dataset-level caches + update/rebuild)

### Add file
- `src/kymflow/core/zarr/kym_dataset.py`

### Core responsibilities
- Wrap a `kymflow_zarr.ZarrDataset`
- Hold in-memory caches for dataset tables:
  - `self.tables: dict[str, pd.DataFrame]`
- Provide methods:
  - `load_tables(names: list[str] | None = None) -> None`
  - `get_table(name: str) -> pd.DataFrame`
  - `save_table(name: str) -> None` (write cache back)
  - `save_all_tables() -> None`
  - `rebuild(indexer: DatasetIndexer, *, image_ids: list[str] | None = None) -> pd.DataFrame`
    - loops records and concatenates rows
    - writes dataset table via `ZarrDataset.save_table`
    - updates cache
  - `update_image(indexer: DatasetIndexer, image_id: str) -> pd.DataFrame`
    - loads record
    - computes rows for that image
    - calls `ZarrDataset.replace_rows_for_image_id`
    - updates in-memory cache accordingly
  - `update_images(indexer, image_ids: list[str])` (batch helper, optional)

### Acceptance
- Uses `extract_rows(rec)` (record-level)
- Does not do any domain analysis; only reads per-image artifacts and builds indices

---

## Ticket KD3 — First indexer: `VelocityEventsIndexer` (derived from per-image events artifact)

### Add file
- `src/kymflow/core/zarr/indexers/velocity_events.py`

### Behavior
- `table_name = "velocity_events"`
- `extract_rows(rec)`:
  - attempt to load per-image table artifact from record analysis:
    - try `rec.load_df_parquet("velocity_events")` or equivalent
    - if missing, return empty DataFrame with required columns
  - ensure returned rows include `image_id` column (fill with rec.image_id)
- Required cols (suggested):
  - `image_id`, `roi_id`, `event_id`, `t0_s`, `t1_s`, `kind`, `score` (adjust later)

### Acceptance
- Works with partially populated datasets (missing artifact returns empty)

---

## Ticket KD4 — Second indexer: `RadonReportIndexer` (derived from per-image radon report artifact)

### Add file
- `src/kymflow/core/zarr/indexers/radon_report.py`

### Behavior
- `table_name = "radon_report"`
- `extract_rows(rec)`:
  - load per-image radon report artifact (table or dict)
  - preferred: per-image table parquet `radon_report.parquet`
  - if you only have dict today: convert dict->one-row DataFrame
  - add `image_id` column
- Required cols: keep minimal and allow extension:
  - `image_id`, `mean_velocity`, `median_velocity`, `n_valid`, `notes` (example; adjust later)

### Acceptance
- Handles dict or table form; chooses table if present

---

## Ticket KD5 — Demo + tests for KymDataset and indexers

### Add tests
- `src/kymflow/core/zarr/tests/test_kym_dataset_indexers.py`

Test plan:
1) Create a temp dataset with 2–3 records (small arrays)
2) For each record, save per-image artifacts:
   - `velocity_events` table (parquet) for some records
   - `radon_report` dict or table for all records
3) Build `KymDataset` and run:
   - `rebuild(VelocityEventsIndexer)` → dataset table has correct rows and image_id included
   - modify one record’s per-image events table, call `update_image(...)` and verify dataset table updates only that image rows
4) Ensure caches reflect saved tables.

### Add demo
- `src/kymflow/core/zarr/examples/demo_kym_dataset_v01.py`
Show:
- open dataset
- rebuild radon + velocity tables
- iterate results
- simulate edit of one record and update index

---

## Integration note (future)
Once KymDataset exists, your GUI “Refresh” button flow becomes:
1) `new_ids = ds.refresh_from_folder(path)`
2) `kds.update_images(indexer, new_ids)` for each indexer you care about

---

# Notes for Codex
- Keep public method docstrings clear and typed.
- Keep storage logic inside `kymflow_zarr`; keep orchestration in `kymflow.core`.
- Do not embed UI concerns in KymDataset.
