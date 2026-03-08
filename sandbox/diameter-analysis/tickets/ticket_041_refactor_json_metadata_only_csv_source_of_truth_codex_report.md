# Ticket 041 Codex Report

## Summary of what you changed (high-level)
Refactored sidecar serialization to make CSV the single source of per-row results and JSON metadata-only.

- Bumped sidecar schema to v2 and enforced strict `schema_version == 2` on load.
- Replaced JSON `runs[*].results` payloads with metadata-only `rois` entries.
- Dropped `_ch{channel}` suffix from wide CSV columns (`*_roi{roi}` now canonical).
- Loader now uses JSON metadata for ROI→channel mapping and ROI bounds, then reconstructs results from CSV only.
- Added ROI-skip behavior for missing required CSV columns with `logger.error(...)` messages and GUI warning notifications.

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
  - Added constants/logger:
    - `DIAMETER_SIDECAR_SCHEMA_VERSION = 2`
    - module `logger`
  - Updated wide CSV naming:
    - `WIDE_COLUMN_RE` now matches `{field}_roi{roi}`
    - `WideCsvRegistry.columns(...)` emits `_roi{roi}` suffix only
    - `WideCsvRegistry.parse_columns(...)` now parses by ROI only
  - Updated `bundle_from_wide_csv_rows(...)`:
    - now requires `roi_to_channel` mapping
    - reconstructs `(roi_id, channel_id)` run keys from ROI columns + mapping
  - Refactored `save_diameter_analysis(...)`:
    - requires `roi_bounds_by_run` and `detection_params_by_run`
    - writes JSON metadata-only structure:
      - `schema_version`
      - `source_path`
      - `rois` keyed by ROI id, each with `channel_id`, `roi_bounds_px`, `detection_params`
    - no JSON per-row `results`
  - Refactored `load_diameter_analysis(...)`:
    - strict `schema_version == 2`
    - strict required JSON keys under each ROI metadata entry
    - builds `roi_to_channel` from JSON metadata
    - validates required CSV columns per JSON ROI
    - missing required CSV columns for an ROI -> skip ROI, append warning message, `logger.error(...)`
    - loads results from CSV only
    - returns:
      - `bundle`
      - `detection_params_by_run`
      - `roi_bounds_by_run`
      - `warnings`

- `kymflow/sandbox/diameter-analysis/gui/controllers.py`
  - `load_selected_path(...)` now returns loader warnings list.
  - `save_analysis(...)` now passes:
    - `roi_bounds_by_run`
    - `detection_params_by_run`
  - `try_load_saved_analysis(...)` updated for new loader return signature and warning propagation.
  - On file select, runtime detection params/results are refreshed from loaded sidecars when run `(roi=1, ch=1)` exists.

- `kymflow/sandbox/diameter-analysis/gui/views.py`
  - File-select handler now shows warning `ui.notify(...)` messages returned by controller loader.
  - Existing refresh hook still updates Detection Params editor from runtime state.
  - Save success notify remains filename-only for save action.

- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
  - Updated wide CSV tests to `_roi` naming.
  - Updated `bundle_from_wide_csv_rows(...)` calls with required `roi_to_channel`.
  - Updated sidecar save/load tests for new API/signature and JSON `rois` schema.
  - Added assertions for loaded `roi_bounds_by_run` and strict JSON metadata behavior.

- `kymflow/sandbox/diameter-analysis/tests/test_controller_save_analysis.py`
  - Updated save monkeypatch signature to include `roi_bounds_by_run`.
  - Added assertions for full-image ROI bounds used by current GUI save path.
  - Updated load monkeypatch signature to new 4-tuple return and warning propagation.

- `kymflow/sandbox/diameter-analysis/docs/multi_run_serialization.md`
  - Updated documentation to sidecar JSON metadata-only v2.
  - Updated CSV naming examples to `_roi` (no `_ch`).

## Exact validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest tests/test_multi_run_serialization.py tests/test_controller_save_analysis.py -q`
- Result: PASS
- Summary: `24 passed, 1 warning in 0.69s`

2. `uv run pytest`
- Result: PASS
- Summary: `106 passed, 1 warning in 1.87s`

## Assumptions made
- Current GUI still targets single active run `(roi=1, ch=1)`; multi-ROI metadata is preserved but GUI load applies active run only.
- Current save path uses full image bounds `(0, n_time, 0, n_space)` for stored `roi_bounds_px` in GUI flow.

## Risks / limitations / what to do next
- Loader skip behavior is implemented at backend logging + returned warnings; GUI warning notifications currently occur on file selection path using returned messages.
- If ROI-specific partial column subsets become common, a dedicated user-facing summary panel may improve visibility beyond per-warning toasts.

## Views regression guardrail confirmation
- `gui/views.py` was modified.
- **Post Filter Params card remains present and functional** (no card removal/structural regression; only file-select warning notify plumbing changed).

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
