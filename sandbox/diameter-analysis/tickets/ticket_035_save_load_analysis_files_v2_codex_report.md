# Ticket 035 Codex Report

## Summary of what you changed (high-level)
Implemented manual, fail-fast diameter sidecar persistence for one kym path using two files:
- JSON sidecar: `<kym_stem>.diameter.json`
- CSV sidecar: `<kym_stem>.diameter.csv`

Added backend APIs for save/load, validated JSON+CSV consistency on load, and wired a GUI **Save analysis** button that calls a controller method (no autosave).

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
  - Added sidecar path helper:
    - `_diameter_sidecar_paths(kym_path, sidecar_dir=None)`
  - Added backend API:
    - `save_diameter_analysis(kym_path, bundle, out_dir=None) -> (json_path, csv_path)`
    - `load_diameter_analysis(kym_path, in_dir=None) -> DiameterAnalysisBundle`
  - Save behavior:
    - writes JSON bundle (`bundle.to_dict()`) plus `source_path` metadata,
    - writes wide CSV from registry-driven `bundle_to_wide_csv_rows(...)`.
  - Load behavior:
    - fail-fast validates JSON object and bundle required fields via `DiameterAnalysisBundle.from_dict(...)`,
    - parses CSV via `bundle_from_wide_csv_rows(...)`,
    - validates JSON/CSV consistency for schema_version, run keys, and per-run lengths.

- `kymflow/sandbox/diameter-analysis/gui/controllers.py`
  - Added `AppController.save_analysis()`:
    - fail-fast if no results,
    - fail-fast if no loaded kym path,
    - builds `DiameterAnalysisBundle` for current run and calls `save_diameter_analysis(...)`.

- `kymflow/sandbox/diameter-analysis/gui/views.py`
  - Added Home page button:
    - `Save analysis` -> `controller.save_analysis` via `_safe_run(...)`.
  - This is manual save only (no autosave on detect/load).

- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
  - Added `test_save_load_diameter_analysis_roundtrip_sidecars`:
    - verifies sidecar naming and roundtrip integrity for multi-run bundle.
  - Added `test_load_diameter_analysis_fails_when_run_required_key_missing`:
    - removes required run `channel_id` in JSON and asserts fail-fast on load.

- `kymflow/sandbox/diameter-analysis/tests/test_controller_save_analysis.py` (new)
  - Added controller tests:
    - fail-fast when no results,
    - verifies backend save call uses loaded kym path and expected run key `(1, 1)`.

## Exact validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest tests/test_multi_run_serialization.py tests/test_controller_save_analysis.py -q`
- Result: PASS
- Summary: `17 passed, 1 warning in 0.56s`

2. `uv run pytest`
- Result: PASS
- Summary: `99 passed, 1 warning in 1.69s`

## Assumptions made
- Manual save targets currently selected/loaded kym path (`state.loaded_path`); synthetic/no-path state fails fast.
- GUI save path override (`out_dir`) is backend-capable but not exposed in GUI for this ticket.
- Consistency check requirement is satisfied by schema version, run-key set, and per-run length matching between JSON and CSV sidecars.

## Risks / limitations / what to do next
- `AppController.save_analysis()` currently serializes only the current in-memory run `(roi=1, ch=1)` from GUI state, while backend format supports multi-run bundles.
- GUI currently surfaces a generic `OK` toast via `_safe_run`; returned save file paths are not displayed to the user.
- If needed next: add explicit UI feedback with saved JSON/CSV paths.

## Views regression guardrail confirmation
- `gui/views.py` was modified.
- **Post Filter Params card remains present and functional** (no logic changes to its card/editor wiring).

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
