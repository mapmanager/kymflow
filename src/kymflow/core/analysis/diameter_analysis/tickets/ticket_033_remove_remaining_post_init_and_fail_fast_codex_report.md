# Ticket 033 Codex Report

## Summary of what changed
Implemented a fail-fast cleanup for remaining coercive behavior in `diameter_analysis.py` dataclass paths, focused on removing silent coercions in `__post_init__` logic and tightening construction-boundary validation.

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
  - Tightened helper validators to reject silent coercions:
    - `_normalize_optional_float` now rejects non-numeric non-None inputs.
    - `_normalize_float_list` now rejects non-numeric entries before float conversion.
    - `_normalize_bool_list` now requires actual `bool` entries (no `bool(value)` coercion).
    - Added `_require_numeric` and `_require_positive_numeric` for strict numeric checks.
  - `DiameterAlignedResults.__post_init__`:
    - Removed coercive scalar normalization (`int(...)`, `float(...)`, `str(...)`) for required fields.
    - Added explicit fail-fast validation for schema/source/path/roi/channel/units.
    - Kept aligned-length checks and derived `qc_any_violation` generation.
    - Added explicit validation that trace lists/flags are already valid rather than silently repaired.
  - `DiameterResult.from_dict`:
    - Replaced generic `dataclass_from_dict` path with explicit required-key checks and strict type validation.
    - Rejects string IDs and non-bool flag fields.
  - `DiameterResult.from_row`:
    - Removed back-compat defaults (`row.get(..., default)`) for required fields.
    - Requires all `ROW_FIELDS` keys; allows empty `qc_flags` string but no missing required numeric/bool fields.
  - `DiameterRunKey.__post_init__`:
    - Removed `object.__setattr__` normalization; now validation-only.
  - `DiameterAnalysisBundle.__post_init__` and `from_dict`:
    - Removed `int(...)` schema coercion; now strict `_require_int` fail-fast behavior.
- `kymflow/sandbox/diameter-analysis/tests/test_results_aligned_schema.py`
  - Added `test_aligned_results_rejects_non_int_roi_id`.
  - Added `test_aligned_results_rejects_non_bool_qc_flags`.
- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
  - Added `test_bundle_from_dict_rejects_non_int_schema_version`.
- `kymflow/sandbox/diameter-analysis/tests/test_required_roi_channel_analyze_v2.py`
  - Added `test_from_row_fails_fast_when_required_non_id_field_missing`.
  - Added `test_from_dict_rejects_string_roi_id`.

## Exact validation commands run + results
Ran from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- Result: PASS
- Summary: `91 passed, 1 warning in 1.88s`

## Assumptions made
- `qc_flags` remains a required CSV column, but an empty string value is valid and maps to an empty list.
- Strict fail-fast behavior should reject non-`bool` QC arrays and non-int schema/ROI/channel IDs instead of coercing them.

## Risks / limitations / what to do next
- `DiameterAlignedResults.from_dict` still uses the shared generic dataclass deserializer path; strictness is now enforced by `__post_init__`, but future cleanup could move this class to fully explicit `from_dict` parsing for consistency.
- If external payload producers relied on legacy fallback columns/defaults in `DiameterResult.from_row`, they now fail fast and must emit complete required columns.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
