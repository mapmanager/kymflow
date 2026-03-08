# Ticket 045 — Fix save/load regressions + enforce metadata-only JSON contract

## Context
After recent serialization refactors (tickets 041–044), the goal is:
- **CSV is the sole source of truth for per-timepoint results**.
- **JSON is metadata-only** (schema_version, source_path, per-ROI metadata: channel_id, roi_bounds_px, detection_params).
- Loader is **tolerant of extra unrelated CSV columns**, but **strict for declared ROIs**: if JSON declares ROI X, required ROI-X columns must exist in CSV or ROI X is **skipped with loud error**.
- **No backward-compat defaults** for required fields (roi/channel/bounds) and no dual-format parsing.

Current code has apparent regressions/typos that must be fixed before we build more features:
- `save_diameter_analysis(...)` ends with an extraneous token (`re`) which should not exist.
- `load_diameter_analysis(...)` returns an undefined / truncated variable name (`roi_boun`) instead of the ROI bounds mapping.

These must be corrected and covered by tests.

## Goals
1. **Fix save/load correctness** (no stray tokens, no undefined return vars).
2. **Lock in the metadata-only JSON contract** (no per-row results in JSON; no dual schema parsing).
3. **Add regression tests** so these issues cannot reappear.

## Non-goals
- No algorithm changes to diameter detection.
- No GUI work (other than whatever import paths must change due to refactors).

## Scope of work

### A) Fix `save_diameter_analysis(...)` implementation
- Remove the stray `re` token at end of function.
- Ensure function returns a stable result (e.g., `(json_path, csv_path)` or whatever the current API is) and that callers/tests match.

### B) Fix `load_diameter_analysis(...)` return value + typing
- Replace `return bundle_csv, detection_params_out, roi_boun` with:
  - `return bundle_csv, detection_params_out, roi_bounds_out`
- Ensure `roi_bounds_out` is fully populated for **every ROI that successfully loads**.

### C) Fail-fast rules (no silent defaults)
- Do not use fallbacks like `row.get("channel_id", "1")` for required fields.
- Any missing required metadata for a JSON-declared ROI (roi_bounds_px, channel_id, detection_params) should cause that ROI to be skipped with loud error (or fail fast globally if that is current policy — keep consistent with existing loader policy).

### D) Tests
Add/adjust tests to cover:
1. **Round-trip save→load works** for a simple bundle with one ROI.
2. **Loader skip behavior**:
   - JSON declares ROI1 + ROI2, but CSV missing ROI1 required columns → ROI1 skipped, ROI2 loads, loud error emitted.
3. **Contract enforcement**:
   - JSON must not contain per-row results.
   - Loader must not attempt dual-format parsing.

Notes:
- If your current tests already cover some of this, extend them minimally.
- Prefer adding the smallest new tests that specifically catch the two regressions (stray token in save; undefined return var in load) + one behavioral contract test.

## Acceptance criteria
- All tests pass.
- `save_diameter_analysis(...)` contains no stray tokens and produces usable files.
- `load_diameter_analysis(...)` returns `(bundle_csv, detection_params_out, roi_bounds_out)` with correct values.
- No silent defaults for roi/channel/bounds/detection_params.
- Metadata-only JSON contract is enforced (no per-row results stored/loaded).
