# codex_ticket_26_29.md

## Scope
This bundle does **two** things:

1) **Step 1 — Tighten incremental correctness further (optional hardening)**  
2) **Step 2 — First real end-to-end pipeline demo (folder → zarr ingest → table → NiceGUI viewer)**

Target environment:
- Python 3.11+
- NiceGUI **3.7.1** (AG Grid behavior is version-sensitive)
- Use the project’s existing `kymflow_zarr` storage primitives and the new dataset-table/indexer framework.
- Follow the AG Grid construction pattern in `gold_standard_aggrid_v2.py` **exactly** (do not “simplify”).

---

## Ticket 26 — Incremental correctness hardening (event detectors, 0-row results, staleness edge cases)

### Goals
- Make incremental updates correct even when:
  - An analysis runs successfully and returns **0 rows** (e.g., no events detected)
  - A record previously had rows, but now should have 0 rows after rerun
  - Rows exist in the table for an image_id but the record has no per-image artifact yet (table-first edge)
- Make “stale” status more explicit for debugging and UI.

### Requirements
1) **Add explicit “analysis_run” marker semantics for indexers**
   - Each indexer must be able to mark that it ran, even if output table rows are empty.
   - Add a small, standard payload stored per-image (record-level) under something like:
     - `analysis/<indexer_name>_run.json` (raw JSON, not gz)
   - Contents must minimally include:
     - `indexer_name`
     - `params_hash`
     - `ran_utc_epoch_ns` (or local epoch ns)
     - `status` (e.g. "ok")
     - `n_rows` (0 allowed)

2) **Update the incremental algorithm to handle “0 rows is real output”**
   - If indexer ran with current `params_hash` and produced 0 rows:
     - Dataset table should have **no rows** for that image_id **AND**
     - The run marker exists and indicates `n_rows=0`.
   - If table has rows but run marker says `n_rows=0` for same params_hash:
     - treat as inconsistent → rebuild/replace rows from source-of-truth.
   - If run marker missing:
     - treat as unknown → stale.

3) **Staleness API improvements**
   - Ensure there is a per-image staleness result object (or dict) with:
     - `has_run_marker`
     - `table_rows_present`
     - `params_hash_matches`
     - `is_stale` (final)
     - `reason` (short string enum)
   - Expose via something like `KymDataset.get_staleness(table_name, image_id, params_hash)`.

### Tests
Add/extend tests to prove:
- “0 events” case persists marker + leaves no rows, but not considered stale.
- Rerun that produces 0 rows correctly removes prior rows.
- Missing marker makes stale true.
- Marker+table mismatch triggers rebuild.

---

## Ticket 27 — Raw JSON artifacts (write .json; read .json and legacy .json.gz)

### Goals
- All new JSON artifacts written by `kymflow_zarr` should be **raw `.json`** (human-browsable).
- Reads should be backward compatible with `.json.gz`.

### Requirements
1) In `ArtifactStore` / zarr store implementation:
   - Prefer writing `*.json` for dict payloads.
   - When loading:
     - If `name.json` exists → load it
     - else if `name.json.gz` exists → load it
     - else missing

2) Update any callers that hardcode `.json.gz` names to use logical artifact names (store decides extension).

### Tests
- Write `.json`, read it back.
- Ensure reading legacy `.json.gz` still works.

---

## Ticket 28 — Pipeline demo CLI (folder → ingest new files → update manifest → build dataset tables)

### Goals
- A practical script that matches your real workflow:
  1) Point at a folder containing many TIFFs
  2) Create/open dataset.zarr
  3) Ingest **new** TIFFs (skip duplicates by provenance checks)
  4) Update manifest
  5) Run indexers to build/update dataset tables
  6) Export legacy CSV/JSON/TIFF if requested

### Requirements
1) Add a new example script:
   - `src/kymflow/core/zarr/examples/demo_pipeline_cli_v01.py`
2) CLI args (argparse is fine):
   - `--input <folder>`
   - `--dataset <path/to/dataset.zarr>`
   - `--ingest-new-only` (default true)
   - `--run-indexers velocity_event` (comma list; default: all registered)
   - `--export-legacy <folder>` (optional)
3) Duplicate detection (minimum viable):
   - Use record provenance fields already in metadata/artifacts:
     - `original_path` (string)
     - optional `file_size`, `mtime_ns`
   - If a TIFF with same `original_path`+`file_size`+`mtime_ns` already exists, skip ingest.
   - Do **not** auto-delete anything.

### Acceptance checks
- Running script twice on same folder results in:
  - First run ingests
  - Second run ingests 0 new images (prints summary)

---

## Ticket 29 — NiceGUI viewer demo (AG Grid + Plotly heatmap) using gold-standard AG Grid

### Goals
- A minimal but real NiceGUI app that:
  - Loads a dataset.zarr
  - Shows a table (manifest-derived + selected table columns) in AG Grid
  - Clicking a row loads image pixels and displays a Plotly heatmap
  - Shows basic metadata panel (header, experiment metadata, ROI counts)

### Non-negotiable constraints
- **Use NiceGUI 3.7.1**
- **Construct AG Grid using the exact pattern** from `gold_standard_aggrid_v2.py`:
  - `ui.aggrid.from_pandas(df).classes("w-full aggrid-compact")`
  - set `columnDefs`, `rowSelection`, `:getRowId` etc
  - call `aggrid.update()`
  - attach events via `aggrid.on(...)`
  - optional `ui.context_menu()` attached to a container for column toggles
- Do **not** “optimize” or “simplify” AG Grid initialization.

### Requirements
1) Add example app:
   - `src/kymflow/core/zarr/examples/demo_nicegui_viewer_v01.py`

2) Data shown in grid
   - Build a pandas DataFrame with at least:
     - `image_id`
     - `original_path` (if available)
     - `acquired_local_epoch_ns` (or friendly derived column)
     - plus a few columns from a dataset table if present (e.g. velocity_event summary)
   - Use `unique_row_id_col="image_id"`.

3) Plotly heatmap
   - Implement a pure function:
     - `def plot_heatmap_dict(arr: np.ndarray, *, title: str = "") -> dict:`
   - Must return plotly **dict** (not go.Figure).
   - Viewer calls `ui.plotly(plot_dict)` and updates it on selection.

4) Modular structure
   - Keep UI thin; put dataset read logic into helper functions (no domain analysis).
   - Avoid global mutable state; use a small controller class if needed.

### Demo run command
- Document a run command in the file header, e.g.:
  - `uv run python src/kymflow/core/zarr/examples/demo_nicegui_viewer_v01.py --dataset ...`

### Tests
- No UI tests required.
- Add a small smoke test for the DataFrame-building function (pure function), if feasible.

---

## Definition of Done
- All tests pass:
  - `uv run pytest src/kymflow/core/zarr/tests -q`
- New CLI demo runs and is idempotent on second run
- NiceGUI demo launches and displays:
  - grid rows
  - click → heatmap update
  - metadata panel updates
- JSON artifacts are written as `.json` (new) and legacy `.json.gz` still loads
