# Ticket 037 Codex Report

## Summary of what you changed (high-level)
Implemented a single-source-of-truth wide CSV registry pathway for both emit and parse flows.

- Added canonical registry object with `columns(...)` and `parse_columns(...)`.
- Refactored wide CSV write/read callsites to use registry methods only.
- Added fail-fast unknown wide-field rejection with clear error listing.
- Updated tests to lock registry behavior and unknown-field handling.
- Updated docs to match parser behavior.

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
  - Added `WideCsvRegistry` dataclass with:
    - `columns(run_keys, include_time=True, include_qc=True)`
    - `parse_columns(header)`
  - Added canonical `WIDE_CSV_REGISTRY` instance.
  - Updated `bundle_to_wide_csv_rows(...)` to generate headers via `WIDE_CSV_REGISTRY.columns(...)`.
  - Updated `bundle_from_wide_csv_rows(...)` to parse columns via `WIDE_CSV_REGISTRY.parse_columns(...)`.
  - Parser behavior now:
    - rejects unknown wide columns matching pattern (e.g., `bogus_field_roi1_ch1`),
    - ignores unrelated non-wide columns.

- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
  - Imported `WIDE_CSV_REGISTRY`.
  - Added `test_wide_csv_registry_columns_snapshot_single_run`.
  - Added `test_wide_csv_loader_rejects_unknown_wide_field`.
  - Added `test_wide_csv_loader_ignores_unrelated_non_wide_columns`.

- `kymflow/sandbox/diameter-analysis/docs/multi_run_serialization.md`
  - Documented parser behavior for unknown wide columns vs unrelated non-wide columns.

## Exact validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- Result: PASS
- Summary: `95 passed, 1 warning in 1.76s`

## Assumptions made
- For unrelated header columns that do not match the wide pattern, ignoring them is acceptable default behavior.
- Unknown columns are only considered errors when they match the wide-pattern naming convention.

## Risks / limitations / what to do next
- The registry currently governs wide CSV headers/parsing in `diameter_analysis.py`; if additional wide CSV entry points are added later, they must use `WIDE_CSV_REGISTRY` to avoid drift.
- Optional next step: expose registry helper docs/examples for contributors adding new wide fields.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
