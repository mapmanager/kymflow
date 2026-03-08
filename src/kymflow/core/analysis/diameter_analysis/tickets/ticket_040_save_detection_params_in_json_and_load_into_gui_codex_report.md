# Ticket 040 Codex Report

## Summary of what you changed (high-level)
Implemented strict per-run detection-params persistence in `.diameter.json`, strict load-time reconstruction of those params, and GUI/runtime wiring so selecting a file restores analysis results + detection params into controller state and the Detection Params editor.

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
  - Updated sidecar save API:
    - `save_diameter_analysis(..., *, detection_params_by_run, out_dir=None)` now requires detection params for each run.
  - Sidecar JSON format now stores per run:
    - `roi_id`, `channel_id`, `detection_params`, `results`.
  - Updated load API:
    - `load_diameter_analysis(...) -> (bundle, detection_params_by_run)`.
  - Load is fail-fast for missing required run keys, including `detection_params`.
  - Preserved strict key/id validation and JSON/CSV consistency checks.

- `kymflow/sandbox/diameter-analysis/gui/controllers.py`
  - `load_selected_path(...)` now attempts sidecar load after TIFF load via `try_load_saved_analysis()`.
  - `save_analysis()` now requires detection params and passes per-run params to `save_diameter_analysis(...)`.
  - Added `try_load_saved_analysis()`:
    - checks sidecar existence,
    - loads `(bundle, detection_params_by_run)`,
    - sets `state.results` and `state.detection_params` for `(roi=1, ch=1)`,
    - rebuilds figures and emits state.

- `kymflow/sandbox/diameter-analysis/gui/views.py`
  - Detection params editor refresh now also runs on state refresh, so loaded params are reflected in the UI controls.
  - `_safe_run(...)` now shows save success as filenames only when a save returns `(json_path, csv_path)`:
    - `Saved: <json_name>, <csv_name>`.

- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
  - Updated sidecar save/load tests for new API and return type.
  - Added strict test that missing per-run `detection_params` in JSON raises.
  - Asserts loaded `detection_params_by_run` equals saved values.

- `kymflow/sandbox/diameter-analysis/tests/test_controller_save_analysis.py`
  - Updated save call test for required `detection_params_by_run` argument.
  - Added test for `try_load_saved_analysis()` populating runtime `results` + `detection_params`.

## Exact validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest tests/test_multi_run_serialization.py tests/test_controller_save_analysis.py -q`
- Result: PASS
- Summary: `24 passed, 1 warning in 0.63s`

2. `uv run pytest`
- Result: PASS
- Summary: `106 passed, 1 warning in 1.81s`

## Assumptions made
- For current GUI flow, the active run is `(roi=1, ch=1)` and loaded params/results are applied from that run key.
- Sidecar load should be attempted automatically on file select only when both `.diameter.json` and `.diameter.csv` exist.

## Risks / limitations / what to do next
- Multi-run sidecars are fully parsed, but GUI currently activates only `(roi=1, ch=1)` by design.
- If future GUI supports selectable ROI/channel runs, controller should expose run-switching using loaded `detection_params_by_run` and `bundle.runs`.

## Views regression guardrail confirmation
- `gui/views.py` was modified.
- **Post Filter Params card remains present and functional** (card layout and wiring preserved).

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
