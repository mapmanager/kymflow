# Ticket 044 Codex Report

## Summary of what you changed (high-level)
Completed the metadata-only JSON + wide CSV single-path contract by tightening loader schema requirements and explicit undeclared-ROI CSV handling.

- Kept a single save/load pathway (`save_diameter_analysis` / `load_diameter_analysis`) with JSON metadata-only and CSV as results source of truth.
- Enforced strict required JSON key `source_path` (string) on load.
- Added explicit warning behavior when CSV contains ROI-wide columns for ROIs not declared in JSON metadata (ignored, not hard-fail).
- Preserved skip-ROI behavior for missing required CSV columns with loud `logger.error(...)` and warnings list.

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
  - `load_diameter_analysis(...)`:
    - Added fail-fast check for missing required `source_path`.
    - Added fail-fast check for non-string `source_path` (required type).
    - Added `logger.warning(...)` when ignoring wide CSV columns for undeclared ROIs.
  - Existing strict checks retained:
    - schema_version exact match
    - required `rois` mapping
    - legacy `runs`/`results` key rejection
    - required per-ROI metadata keys
    - missing required ROI CSV columns => skip ROI + `logger.error(...)`

- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
  - Added `test_load_diameter_analysis_fails_when_source_path_missing`.
  - Extended `test_load_diameter_analysis_ignores_extra_roi_columns_not_in_json` to assert warning logging for ignored undeclared ROI columns.
  - Existing tests for legacy-key rejection and ROI skip behavior remain and pass.

## Exact validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`.

1. `uv run pytest tests/test_multi_run_serialization.py -q`
- Result: PASS
- Summary: `21 passed, 1 warning in 0.41s`

2. `uv run pytest`
- Result: PASS
- Summary: `106 passed, 1 warning in 1.80s`

## Assumptions made
- For ROI identity in JSON metadata, loader uses ROI dict key as canonical ID (`rois["<roi_id>"]`), consistent with current saved schema.
- Requirement for extra CSV ROI columns is implemented as ignore + warning, not hard-fail.

## Risks / limitations / what to do next
- JSON metadata currently infers ROI ID from `rois` keys (does not store a separate `roi_id` field in each ROI object). This is consistent with current schema, but if a future schema requires explicit `roi_id`, both save/load and tests should be updated together.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
