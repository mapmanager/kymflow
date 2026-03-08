# Ticket 042 Codex Report

## Summary of what you changed (high-level)
Removed the remaining legacy JSON-results save/load pathway and kept a single metadata-only JSON + CSV results system.

- Removed legacy `DiameterAnalyzer.save_analysis(...)` / `DiameterAnalyzer.load_analysis(...)` (`analysis_params.json` + `analysis_results.csv`).
- Removed bundle JSON serialization that used `runs[*].results` (`DiameterAnalysisBundle.to_dict/from_dict`).
- Kept GUI on the existing sidecar API path (`save_diameter_analysis` / `load_diameter_analysis`) only.
- Updated tests to use metadata-only `.diameter.json` + CSV-based result reconstruction.

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
  - Removed `RUN_KEY_RE`, `_run_key_to_str`, `_run_key_from_str` helpers.
  - Removed `DiameterAnalysisBundle.to_dict()` / `DiameterAnalysisBundle.from_dict()` JSON pathway (`runs/results`).
  - Removed legacy `DiameterAnalyzer.save_analysis(...)` and `DiameterAnalyzer.load_analysis(...)` methods.

- `kymflow/sandbox/diameter-analysis/tests/test_analysis_hardened.py`
  - Replaced legacy save/load roundtrip test with sidecar roundtrip via `save_diameter_analysis(...)` and `load_diameter_analysis(...)`.
  - Updated expected filenames to `<stem>.diameter.json` and `<stem>.diameter.csv`.

- `kymflow/sandbox/diameter-analysis/tests/test_required_roi_channel_analyze_v2.py`
  - Replaced legacy `DiameterAnalyzer.save_analysis/load_analysis` usage with sidecar API.
  - Assertions now validate ROI/channel preservation through loaded bundle runs.

- `kymflow/sandbox/diameter-analysis/tests/test_post_filter_diameter.py`
  - Replaced legacy save/load test with sidecar roundtrip test.
  - Removed assertion on legacy `post_filter_params_by_roi` JSON payload.

- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
  - Removed obsolete tests that exercised `DiameterAnalysisBundle` JSON `runs/results` serialization.

## Exact validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`.

1. `uv run pytest tests/test_analysis_hardened.py tests/test_required_roi_channel_analyze_v2.py tests/test_post_filter_diameter.py tests/test_multi_run_serialization.py -q`
- Result: PASS
- Summary: `37 passed, 1 warning in 0.50s`

2. `uv run pytest`
- Result: PASS
- Summary: `102 passed, 1 warning in 1.92s`

## Assumptions made
- Ticket 042 requirement to delete JSON structures containing `runs`/`results` applies to the removed bundle JSON serializer (`DiameterAnalysisBundle.to_dict/from_dict`) and legacy `analysis_params.json`/`analysis_results.csv` path.
- Existing GUI save/load route already used sidecar APIs and required no new GUI code edits for this ticket.

## Risks / limitations / what to do next
- This is intentionally breaking for any callers still using removed legacy methods.
- If external scripts still call `DiameterAnalyzer.save_analysis/load_analysis`, they must migrate to `save_diameter_analysis/load_diameter_analysis`.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
