# Ticket 046 Codex Report

## Summary of what you changed (high-level)
Finalized the metadata-only JSON contract by requiring/storing explicit `roi_id` per ROI entry and enforcing key/payload consistency at load time, while preserving CSV-only results loading.

- JSON sidecar save now writes per-ROI `roi_id`.
- JSON sidecar load now requires `roi_id` and validates it matches the ROI dict key.
- Added strict regression tests for schema version fail-fast and ROI id required/mismatch behavior.
- Existing skip-ROI-on-missing-required-CSV-columns behavior and tolerant-extra-columns behavior remain in place and tested.

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
  - `save_diameter_analysis(...)`:
    - Added `"roi_id"` into each JSON `rois[<id>]` entry.
  - `load_diameter_analysis(...)`:
    - ROI required keys now include `roi_id`.
    - Added fail-fast type validation for `roi_id`.
    - Added fail-fast key/payload consistency check:
      - ROI key string (e.g. `"1"`) must match ROI payload `roi_id` integer.

- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
  - Added `test_json_schema_version_fail_fast` (missing/wrong version raises).
  - Added `test_load_diameter_analysis_fails_when_roi_id_missing_or_mismatched`.
  - Strengthened metadata-only JSON assertion in `test_sidecar_json_does_not_store_sum_intensity`:
    - root has no `runs`/`results`
    - each ROI entry includes `roi_id`

## Exact validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`.

1. `uv run pytest tests/test_multi_run_serialization.py -q`
- Result: PASS
- Summary: `25 passed, 1 warning in 0.45s`

2. `uv run pytest`
- Result: PASS
- Summary: `110 passed, 1 warning in 1.82s`

## Assumptions made
- The single supported schema version remains the existing sidecar version constant in code.
- Existing public sidecar API names (`save_diameter_analysis` / `load_diameter_analysis`) are the single active save/load path and were kept.

## Risks / limitations / what to do next
- JSON files missing `roi_id` in ROI metadata now fail fast by design.
- Existing on-disk files generated before this requirement may need regeneration if they omit `roi_id`.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
