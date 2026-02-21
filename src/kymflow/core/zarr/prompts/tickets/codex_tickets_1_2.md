# Codex Tickets — Kymflow Zarr v0.1

These tickets are designed to be pasted into the Codex desktop app.  
Recommended workflow: create a **new git branch** before applying these changes so you don't disrupt your current baseline.

---

## Ticket 1 — Remove legacy `getChannelKeys` usage (without breaking mainline)

### Goal
Clean up the *new v0.1 Zarr/experimental layer* by removing legacy compatibility methods and updating the small number of call sites that currently use them — **but do this on a branch** so your current baseline remains safe.

### Why branch?
This ticket touches:
- `roi.py` (core) and
- a GUI app-state file

Those may affect your existing app if merged directly. On a branch, you can iterate safely and merge only when ready.

### Scope
- Zarr v0.1 experimental store-backed layer:
  - `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/**`
- Core ROI validation:
  - `src/kymflow/core/image_loaders/roi.py` (or actual repo path)
- GUI app-state (wherever it lives)

### Acceptance criteria
1) `AcqImageV01` (or equivalent v0.1 image class) **does not** define:
   - `getChannelKeys`
   - `getImageBounds`
   - `get_img_slice`
   - `mark_metadata_dirty`
   - `is_metadata_dirty`
2) The two known call sites use the new API:
   - `channels_available()`
3) Examples/demos do not call legacy methods.
4) Tests pass:
   - `uv run pytest src/kymflow/core/zarr/tests -q`
5) Avoid adding new broad `except Exception` blocks.

### Files to modify

#### 1) Remove compat methods from v0.1 image class
File:
- `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/acq_image.py`

Actions:
- Remove the legacy/compat methods and dirty tracking API listed above.
- Ensure clean v0.1 API exists:
  - `channels_available(self) -> list[int]`
  - `get_image_bounds(self) -> ImageBounds`
  - `get_channel(self, channel: int = 1) -> np.ndarray` (or keep your chosen existing method name)
- Add/keep type hints and Google-style docstrings.

#### 2) Update ROI channel validation to use new API
File (update to actual path in your repo):
- `src/kymflow/core/image_loaders/roi.py`

Change:
- Replace:
  - `channel_keys = self.acq_image.getChannelKeys()`
- With:
  - `channel_keys = self.acq_image.channels_available()`

#### 3) Update GUI app-state channel loading loop
Find the GUI code doing:
- `channel_keys = kym_file.getChannelKeys()`

Replace with:
- `channel_keys = kym_file.channels_available()`

Also replace any loop that expects old semantics. If `load_channel(channel)` exists, it can stay; if not, update it to the new pixel API.

#### 4) Update examples/demos
File:
- `src/kymflow/core/zarr/examples/demo_gui_flow_v01.py`

Replace legacy calls with:
- `channels_available()`

### Tests to update/add

#### Ensure the clean API is enforced
File:
- `src/kymflow/core/zarr/tests/test_acq_image_compat.py` (rename optional)

Update to assert:
- clean methods exist
- legacy methods do not exist

Example assertions:
- `assert hasattr(img, "channels_available")`
- `assert not hasattr(img, "getChannelKeys")`

#### Ensure ROI validation still works
Add or update a test that:
- creates an image
- asserts channel validation passes for channel 1
- asserts invalid channel raises `ValueError`

### Deliverable
After applying:
- Provide a list of files changed
- Confirm demo runs:
  - `uv run python src/kymflow/core/zarr/examples/demo_gui_flow_v01.py`
- Confirm tests run:
  - `uv run pytest src/kymflow/core/zarr/tests -q`

---

## Ticket 2 — Dataset-level tables + import/export (Zarr as system of record)

### Goal
Make Zarr the system of record by adding:
1) Dataset-level tables (Parquet) for indices/caches (radon report, velocity events, future diameter/HR).
2) Export to a biologist-friendly folder:
   - TIFF per record (exact stored array)
   - per-record artifacts as CSV/JSON
   - dataset-level tables as CSV
3) Import (one-time ingest) from legacy folder structure:
   - TIFF + sidecar artifacts into Zarr records
   - optional rebuild of dataset tables

### Scope
- `kymflow_zarr` dataset/record APIs:
  - `src/kymflow/core/zarr/src/kymflow_zarr/dataset.py`
  - `src/kymflow/core/zarr/src/kymflow_zarr/record.py`
  - `src/kymflow/core/zarr/src/kymflow_zarr/manifest.py` (if needed)
- Zarr artifact store:
  - `src/kymflow/core/zarr/src/kymflow_zarr/experimental_stores/stores/zarr_store.py`
- Add new module(s) for import/export utilities:
  - `src/kymflow/core/zarr/src/kymflow_zarr/io_export.py`
  - `src/kymflow/core/zarr/src/kymflow_zarr/io_import.py`
  (names are suggestions; pick what fits your tree)

### Conventions to implement (v0.1)
Per record (image_id):
- Pixels: `images/<image_id>/data` (zarr array)
- Artifacts: `images/<image_id>/analysis/`
  - dict payloads: `*.json.gz`
  - tables: `*.parquet` (canonical)
Dataset-level:
- tables: `tables/<name>.parquet` (canonical)
- export format: CSV + JSON + TIFF

### Public API to add (ZarrDataset)

#### Dataset tables
Add methods:
- `load_table(self, name: str) -> pandas.DataFrame`
- `save_table(self, name: str, df: pandas.DataFrame) -> None`

Optional helper (recommended):
- `replace_rows_for_image_id(self, name: str, image_id: str, df_rows: pandas.DataFrame, *, image_id_col: str = "image_id") -> None`
  - loads existing table (or empty)
  - drops rows matching image_id
  - appends df_rows
  - saves back

#### Export
Add:
- `export_legacy_folder(self, export_dir: str | Path, *, include_tiff: bool = True, include_tables: bool = True) -> None`

Behavior:
- For each record:
  - write TIFF: `export_dir/images/<image_id>/image.tif` (exact stored array)
  - write metadata dict: `export_dir/images/<image_id>/metadata.json`
  - write per-image tables: `export_dir/images/<image_id>/<name>.csv` (or `.csv.gz`)
  - write per-image dict artifacts: `export_dir/images/<image_id>/<name>.json`
- Dataset tables:
  - `export_dir/tables/<name>.csv`

Notes:
- Use Parquet internally; export uses CSV for human readability.
- Export should be deterministic and idempotent (overwrite files).

#### Import (one-time ingest)
Add:
- `ingest_legacy_folder(self, legacy_root: str | Path, *, pattern: str = "*.tif", include_sidecars: bool = True) -> None`

Behavior:
- Traverse legacy_root recursively for TIFF files.
- For each TIFF:
  - read pixels (tifffile)
  - `rec = self.add_image(arr)` (uuid4)
  - store a provenance dict artifact with source path(s)
  - if sidecars exist (e.g. metadata.json, events.csv, radon_report.csv):
    - ingest them into record analysis/ as dict/table artifacts
- After ingest:
  - optionally `self.update_manifest()`

Do NOT try to infer complex grouping of multi-channel TIFF siblings in v0.1 import. (Can be a v0.2 feature.)

### Tests to add
Under:
- `src/kymflow/core/zarr/tests/`

Add tests for:
1) Dataset table roundtrip:
   - `save_table` then `load_table` equals original
2) `replace_rows_for_image_id` semantics
3) Export writes:
   - TIFF exists for a record
   - metadata json exists
   - a table csv exists when table present
4) Import ingests:
   - creates records
   - persists at least metadata/provenance artifacts if present

### Deliverables
After applying:
- Add example script:
  - `examples/demo_export_import_v01.py`
  that:
  - ingests a small legacy folder
  - exports it
  - reloads dataset and iterates by acquired time

- Confirm tests:
  - `uv run pytest src/kymflow/core/zarr/tests -q`

---

## Notes
- Keep function signatures typed, and Google-style docstrings.
- Prefer Parquet for internal tables; CSV/JSON are import/export formats.
- Keep manifest derived/index-only (rebuildable).
