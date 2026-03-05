# Ticket 039 Codex Report

## Summary of what you changed (high-level)
Extended diameter CSV persistence to include:
- `sum_intensity_roi{roi}_ch{ch}`
- `left_edge_um_roi{roi}_ch{ch}`
- `right_edge_um_roi{roi}_ch{ch}`
- `diameter_um_roi{roi}_ch{ch}`

and updated load/write paths/tests accordingly, while keeping detection algorithms unchanged.

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
  - `DiameterResult`:
    - Added CSV/runtime fields:
      - `sum_intensity: float = math.nan`
      - `um_per_pixel: float = math.nan`
    - Updated `to_dict()` to explicitly exclude `sum_intensity` and `um_per_pixel` so JSON run payloads do not duplicate these per-timepoint signals.
    - Updated `from_dict()` to accept optional `sum_intensity`/`um_per_pixel` when present.
  - `_analyze_center(...)`:
    - Computes `sum_intensity = float(np.sum(profile_proc))` where `profile_proc` is the final binned/windowed profile fed into detection.
    - Stores per-result `um_per_pixel` from analyzer context.
  - Wide CSV registry:
    - Added base fields to `WIDE_CSV_ARRAY_FIELDS`:
      - `sum_intensity`, `left_edge_um`, `right_edge_um`, `diameter_um`
  - `bundle_to_wide_csv_rows(...)`:
    - Emits `_um` columns using `result.<px_field> * result.um_per_pixel`.
    - Emits `sum_intensity` from `result.sum_intensity`.
    - Fails fast if `_um` columns cannot be computed due to non-finite `result.um_per_pixel`.
  - `bundle_from_wide_csv_rows(...)`:
    - Parses `sum_intensity` when present.
    - Derives per-result `um_per_pixel` from available `_um / _px` values when present.
  - `load_diameter_analysis(...)`:
    - Returns the CSV-reconstructed bundle after JSON/CSV consistency checks, so CSV-only per-timepoint signals are available in loaded runtime objects.

- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
  - Added/extended tests to verify:
    - CSV includes `sum_intensity` and `_um` columns.
    - `_um == _px * um_per_pixel`.
    - `sum_intensity == sum(profile_proc)` for analyzed result.
    - Sidecar load roundtrip preserves `sum_intensity`.
    - JSON sidecar does not contain `sum_intensity` in run result entries.

## Exact validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest tests/test_multi_run_serialization.py -q`
- Result: PASS
- Summary: `20 passed, 1 warning in 0.41s`

2. `uv run pytest`
- Result: PASS
- Summary: `104 passed, 1 warning in 1.78s`

## Assumptions made
- The “final binned/windowed profile used as input to diameter detection” maps to `profile_proc` in `_analyze_center(...)` (after windowing/binning and polarity normalization, before threshold/gradient edge logic).
- Keeping `sum_intensity` and `um_per_pixel` as CSV/runtime fields (not JSON-persisted run signals) satisfies the no-duplication JSON requirement for these additions.

## Risks / limitations / what to do next
- `_um` computation at CSV export now requires finite `result.um_per_pixel`; non-analyzer/manual result objects without this value will fail fast when exporting wide CSV.
- `um_per_pixel` reconstruction from CSV is derived from available `_um/_px`; if all px values are zero/NaN for a run, reconstructed `um_per_pixel` may remain NaN.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
