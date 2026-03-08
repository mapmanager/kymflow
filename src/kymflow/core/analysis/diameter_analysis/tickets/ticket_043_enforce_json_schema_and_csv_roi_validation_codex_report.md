# Ticket 043 Codex Report

## Summary of what you changed (high-level)
Implemented strict JSON schema enforcement for sidecar loading and added explicit ROI-column validation coverage in tests.

- Loader now hard-rejects legacy JSON keys (`runs`, `results`).
- Loader behavior for missing ROI CSV columns remains ROI-skip + `logger.error(...)` + warning collection, now covered by direct test.
- Loader tolerates extra CSV ROI columns not declared in JSON metadata (ignored), now covered by direct test.

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
  - In `load_diameter_analysis(...)`:
    - Added fail-fast legacy key check at JSON root:
      - if `runs` or `results` exists, raise `ValueError("Legacy JSON schema detected")`.
    - Added fail-fast legacy key check per ROI payload:
      - if `runs` or `results` exists inside ROI metadata, raise `ValueError`.

- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
  - Added `test_load_diameter_analysis_rejects_legacy_runs_key`.
  - Added `test_load_diameter_analysis_skips_roi_when_csv_columns_missing`:
    - JSON declares ROI1/ROI2, CSV ROI1 columns removed, asserts ROI1 skipped, ROI2 loaded, warning returned, error logged.
  - Added `test_load_diameter_analysis_ignores_extra_roi_columns_not_in_json`:
    - JSON declares only ROI1, CSV still contains ROI2 columns, asserts ROI2 ignored and load succeeds.

## Exact validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`.

1. `uv run pytest tests/test_multi_run_serialization.py -q`
- Result: PASS
- Summary: `20 passed, 1 warning in 0.40s`

2. `uv run pytest`
- Result: PASS
- Summary: `105 passed, 1 warning in 1.76s`

## Assumptions made
- Current canonical JSON schema key for ROI bounds remains `roi_bounds_px` (existing code source of truth), not `roi_bounds`.
- Ticket requirement to forbid legacy structures applies to explicit key rejection for `runs`/`results` keys.

## Risks / limitations / what to do next
- External files/scripts still containing legacy keys (`runs`/`results`) will now fail load immediately by design.
- CSV columns with invalid wide naming (e.g., malformed `_roi`/`_ch`) continue to fail-fast via existing registry validation.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
