# Ticket 038 Codex Report

## Summary of what you changed (high-level)
Implemented negative/tolerance hardening for load behavior focused on strict diameter schema fields and tolerant unrelated extras.

- Added tests for malformed wide schema columns and tolerant extras through sidecar load path.
- Added a minimal parser guard so malformed ROI/CH-like wide columns fail fast.
- Kept behavior tolerant for unrelated non-wide columns and extra JSON keys.

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
  - In `WideCsvRegistry.parse_columns(...)`, added fail-fast rejection for malformed wide-ish columns:
    - If a non-matching header contains `_roi` or `_ch`, raise:
      - `ValueError("Invalid wide CSV column name: ...")`
  - Kept existing behavior:
    - unknown registered-pattern wide fields fail,
    - unrelated non-wide extras are ignored.

- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
  - Added `test_wide_csv_loader_fails_on_malformed_roi_channel_column_name`.
  - Added `test_load_diameter_analysis_tolerates_extra_json_and_csv_columns`.
  - (Existing tests already covered required parts of ticket policy):
    - unrelated extra CSV columns succeed,
    - unknown wide fields fail,
    - missing required run field fails,
    - missing `time_s` fails,
    - JSON missing `channel_id` fails.

## Exact validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest tests/test_multi_run_serialization.py -q`
- Result: PASS
- Summary: `17 passed, 1 warning in 0.42s`

2. `uv run pytest`
- Result: PASS
- Summary: `101 passed, 1 warning in 1.86s`

## Assumptions made
- Columns containing `_roi` or `_ch` are intended to be part of wide diameter schema and should not be treated as unrelated extras if malformed.
- Extra JSON keys should remain tolerated so long as required keys are present and valid.

## Risks / limitations / what to do next
- Strict malformed-name detection currently uses `_roi`/`_ch` token heuristic; this is intentionally conservative for fail-fast schema safety.
- If future schema introduces alternate key tokens, parser heuristics should be updated alongside registry tests.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
