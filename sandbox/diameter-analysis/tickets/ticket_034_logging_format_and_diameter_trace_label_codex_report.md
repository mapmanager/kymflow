# Ticket 034 Codex Report

## Summary of what changed
Implemented the three requested UX updates in `sandbox/diameter-analysis/`:
- Moved GUI logging setup to shared top-level module and updated imports.
- Updated console log format to include level, logger name, function, and line number (no timestamp).
- Updated diameter Plotly trace labels to include analyzed `roi_id` and `channel_id` from results.
- Added unit tests to assert ROI/channel trace labeling for raw and filtered diameter traces.

## File-by-file changes
- `kymflow/sandbox/diameter-analysis/gui/logging_setup.py`
  - Removed (moved).
- `kymflow/sandbox/diameter-analysis/logging_setup.py`
  - New shared logging module location.
  - `configure_logging()` now uses:
    - `"[%(levelname)s] %(name)s:%(funcName)s:%(lineno)d: %(message)s"`
- `kymflow/sandbox/diameter-analysis/gui/app.py`
  - Updated import from `from .logging_setup import configure_logging` to `from logging_setup import configure_logging`.
- `kymflow/sandbox/diameter-analysis/gui/plotting.py`
  - Added `_extract_roi_channel(results)` helper.
  - Added `_format_diameter_trace_name(results, filtered=False)` helper.
  - Updated `make_diameter_figure_dict(...)` trace names:
    - raw: `Diameter (roi <id>, ch <id>)`
    - filtered: `Diameter filtered (roi <id>, ch <id>)`
    - fallback when unavailable: `roi N/A, ch N/A`.
- `kymflow/sandbox/diameter-analysis/tests/test_plotting_trace_labels.py`
  - New tests asserting ROI/channel trace labels for raw and filtered traces.

## Validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`.

1. `uv run pytest -q`
- Result: PASS
- Output summary: `86 passed, 1 warning in 1.67s`

2. `uv run python run_gui.py`
- Result: STARTED (manual interrupt)
- Output observed: `NiceGUI ready to go on http://127.0.0.1:8000`
- Process was then stopped with Ctrl-C (expected for interactive GUI run).

3. `uv run python -c "import logging; from logging_setup import configure_logging; configure_logging(); logging.getLogger('gui.controllers').info('Detect started')"`
- Result: PASS
- Output observed: `[INFO] gui.controllers:<module>:1: Detect started`
- Confirms requested no-timestamp console format and inclusion of logger/function/line fields.

## Assumptions made
- For result payloads without explicit `roi_id`/`channel_id`, trace names should still be deterministic via `roi N/A, ch N/A` fallback.
- For list-based result payloads, ROI/channel are uniform and can be taken from the first result item.

## Risks / limitations / what to do next
- DataFrame payload ROI/channel extraction currently uses the first row when available.
- If mixed ROI/channel data were ever passed into one figure payload, labeling would reflect the first row/item.
- Optional next step: add a defensive check for mixed ROI/channel payloads and raise fail-fast.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
