# ticket_022_results_refactor_aligned_arrays_and_serialization_schema

## Goal
Refactor analysis outputs toward **explicit aligned arrays** (time-indexed vectors) with a **serialization-ready schema** and strong **Google-style docstrings**, so results can be saved/loaded reliably and extended without brittle manual field copying.

This is the follow-on to the “motion constraint QC” work: QC outcomes should be represented as aligned boolean arrays alongside the derived traces.

## Context / Current Problems
- `DiameterResult` and related result objects mix scalars + derived values + partial arrays in ways that are hard to serialize consistently.
- Some serialization helpers (e.g., `to_row()` / `from_row()`) are **brittle**: they hardcode field names, so adding/removing a field silently breaks persistence.
- QC information needs a **canonical place** in the result schema (aligned to frames).

## Scope

### A) Define a canonical results schema with aligned arrays
Update/introduce result dataclasses in `diameter_analysis.py` (or wherever results live) so that for a given ROI analysis we have:

1. **Aligned arrays (length = num_frames)** stored as Python lists (serialization-friendly) or numpy arrays with explicit conversion:
   - `time_s: list[float]` (or `None` if not known; prefer known when real data)
   - `left_um: list[float | None]`
   - `right_um: list[float | None]`
   - `center_um: list[float | None]`
   - `diameter_um: list[float | None]`
2. Optional **post-filtered** aligned array (do NOT move post-filter params into GuiConfig):
   - `diameter_um_filtered: list[float | None] | None`
3. **QC flags as aligned arrays**:
   - `qc_left_edge_violation: list[bool]`
   - `qc_right_edge_violation: list[bool]`
   - `qc_center_shift_violation: list[bool]`
   - `qc_diameter_change_violation: list[bool]`
   - (Optional) `qc_any_violation: list[bool]` (derived)
4. Scalars / metadata (small, stable):
   - `schema_version: int`
   - `source: Literal["synthetic","real"]`
   - `path: str | None`
   - `roi_id: int | None` (real only; synthetic can keep `None`)
   - `channel_id: int | None` (real only; synthetic can keep `None`)
   - geometry/units used for this computation:
     - `seconds_per_line: float`
     - `um_per_pixel: float`

**Rules**
- All aligned arrays must be the same length; enforce via validation (raise `ValueError`).
- Use `None` for missing values instead of `np.nan` in serialization surface.
- For synthetic data, it’s OK to keep `roi_id=None` and `channel_id=None` and treat the full array as the analysis target.

### B) Make serialization DRY and explicit
Create/upgrade helper(s) in `serialization.py`:
- `dataclass_to_dict(dc) -> dict` and `dataclass_from_dict(cls, d: dict)` (if they already exist, use them)
- Add a **single canonical mapping** for row-based persistence if still needed:
  - Either:
    - (Preferred) **drop** `to_row/from_row` and standardize on `to_dict/from_dict`
    - Or keep `to_row/from_row` but implement them using a shared `FIELDS: tuple[str, ...]` and shared conversion helpers (no manual repeated assignments)

Add Google-style docstrings explaining:
- what the schema represents
- what “aligned arrays” means
- what the `schema_version` guarantees
- how missing values are represented

### C) Wire controller plotting to the new aligned arrays (minimal)
Update `gui/controllers.py` plotting and any downstream consumers to read from:
- `result.time_s` + `result.diameter_um` (+ `diameter_um_filtered` when enabled)
- overlays for left/right/center use `left_um/right_um/center_um`

Keep changes minimal and mechanical:
- no UI refactors
- no changes to kymflow boundary rules

### D) Add tests (pytest)
Add/extend tests to validate:
1. **Alignment validation**: mismatched lengths raise.
2. **Serialization roundtrip**:
   - `to_dict` then `from_dict` produces equivalent object
   - lists with `None` survive roundtrip
3. **QC flags alignment**: flags length matches traces.
4. If `to_row/from_row` remains: roundtrip for a single row and schema_version behavior.

## Acceptance Criteria
- Results schema uses aligned arrays as described.
- `uv run pytest` passes.
- No new imports of `kymflow.core.api.kym_external` outside `gui/diameter_kymflow_adapter.py` (boundary tests remain green).
- GUI still displays:
  - kymograph heatmap
  - diameter trace from `diameter_um`
  - overlays from left/right/center arrays (when toggled)

## Out of Scope
- Saving results to disk / UI export flow (planned next ticket).
- Any ROI/channel selection UI (still hard-coded to ROI=1, channel=1 for real).
