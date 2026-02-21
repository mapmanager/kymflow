# codex_ticket_33_35.md

## Title
Core “record summary” accessors + dataset summary joins to thin `viewer_data.build_viewer_dataframe`

Repo: `kymflow`  
Branch: `kymflow-zarr`  
Scope: **core only** (no NiceGUI changes)

### Goals
- Keep UI glue thin by moving **cheap, safe, read-only summary extraction** closer to the storage/domain boundary.
- Do **not** change existing storage primitives behavior.
- Add new helper APIs that:
  - are stable
  - are fast (no pixel reads)
  - tolerate missing artifacts
  - are easy to test

---

## Constraints / Non-negotiables
- Do **not** touch NiceGUI demo code in this ticket.
- Do **not** make breaking changes to `kymflow_zarr` public API.
- Do **not** read image pixels (`rec.load_array()` etc.) for viewer summaries.
- Avoid broad `except Exception` unless immediately re-raised; handle expected missing-artifact cases explicitly.
- Add full type hints + Google docstrings for new functions.

---

## Ticket 33 — Add `RecordSummary` and `summarize_record()` helpers (core domain)

### Problem
`viewer_data.build_viewer_dataframe()` is doing too much: reading per-record metadata, trying to infer fields, mixing marker + manifest + table info. We want a canonical summary shape for UI.

### Deliverables
1) Add a new module:
- `src/kymflow/core/kym_dataset/record_summary.py`

2) Define:
- `@dataclass(frozen=True) class RecordSummary:`
  - `image_id: str`
  - `original_path: str | None`
  - `acquired_local_epoch_ns: int | None`
  - `shape: tuple[int, ...] | None`
  - `dtype: str | None`
  - `axes: tuple[str, ...] | None`
  - `n_rois: int | None`
  - `notes: str | None` (optional: from experiment metadata if present)
  - `has_metadata: bool`
  - `has_rois: bool`
  - `has_header: bool`

3) Implement:
- `def summarize_record(rec: ZarrImageRecord) -> RecordSummary`
  - Must use **only**:
    - manifest-derived info if available
    - metadata payload/header objects if present (but no writes)
    - safe read-only APIs
  - Must tolerate missing header/metadata/rois
  - Must not create groups or write anything
  - Must not require `kymflow` ROI classes if unavailable; if ROI payload exists as list, count length.

4) Tests
- `src/kymflow/core/kym_dataset/tests/test_record_summary.py`
  - record with minimal metadata
  - record missing metadata
  - record with ROI list stored
  - ensure no exceptions; ensure fields match expected

---

## Ticket 34 — Add dataset-level “viewer table builder” that joins manifest + summaries + table aggregates

### Problem
The viewer wants a single DataFrame per dataset for AG Grid. This should not live as a big custom join inside `viewer_data.py`.

### Deliverables
1) Add module:
- `src/kymflow/core/kym_dataset/viewer_table.py`

2) Implement:
- `def build_dataset_view_table(ds: ZarrDataset, *, include_tables: list[str] | None = None) -> pd.DataFrame`

Behavior:
- Base rows come from `ds.image_ids()` / manifest ordering (use acquired ordering if available).
- For each `image_id`, attach `RecordSummary` columns:
  - `image_id`, `original_path`, `acquired_local_epoch_ns`, `shape`, `dtype`, `axes`, `n_rois`, etc.
- If `include_tables` is provided:
  - join selected dataset tables by `image_id`
  - **but** don’t explode rows: aggregate per-image when table has multiple rows.
    - Provide a simple default aggregation per table:
      - `n_rows_<table>` = count rows for image_id
      - optionally `min/max` for a couple numeric columns if obvious (but keep minimal v0.1)
- Return a DataFrame with one row per image_id.

3) Tests
- `src/kymflow/core/kym_dataset/tests/test_viewer_table.py`
  - dataset with 2 records
  - create a dataset table with multiple rows for one image_id
  - ensure view table has 2 rows, includes `n_rows_<table>`

---

## Ticket 35 — Refactor `viewer_data.build_viewer_dataframe()` to be thin wrapper over new helpers

### Problem
We don’t want to break existing call sites yet, but we do want `viewer_data.py` to stop being a thick join layer.

### Deliverables
1) In `src/kymflow/core/kym_dataset/viewer_data.py`:
- Keep the existing public function name:
  - `build_viewer_dataframe(...)`
- Replace the body so it delegates to:
  - `build_dataset_view_table(...)`
- Allow backward-compatible parameters, but route them to `include_tables` where possible.

2) Add/Update tests
- If there are existing tests for `viewer_data.build_viewer_dataframe`, keep them.
- Add one test asserting the function is basically a wrapper (e.g., same columns present).

3) Acceptance
- Viewer demo should work unchanged (but **do not modify demo code** in this ticket).
- Core test suites pass:
  - `uv run pytest src/kymflow/core/zarr/tests -q`
  - `uv run pytest src/kymflow/core/kym_dataset/tests -q`

---

## Definition of Done
- `viewer_data.build_viewer_dataframe()` is reduced to a small wrapper.
- All summary extraction lives in `record_summary.py` and `viewer_table.py`.
- No pixel reads.
- Missing metadata doesn’t crash summaries.
- Tests pass.
