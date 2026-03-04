# Ticket 034 — Improve console log format + add ROI/Channel label to diameter trace

## Goal
Two small UX improvements in `sandbox/diameter-analysis/`:

1) **Console logging:** make console output more informative by including `logger name`, `funcName`, and `lineno` (no timestamp).
2) **Diameter plot label:** when showing the diameter trace in Plotly, include the analyzed **roi_id** and **channel_id** in the trace name/legend label.
3) **Shared logging setup:** move `logging_setup.py` into the main `diameter-analysis/` package so both GUI and backend code can use it, and update imports accordingly.

## Non-goals
- Do not change the detection algorithm.
- Do not change serialization formats.
- Do not refactor unrelated GUI code.

## Boundary rules
- Keep all edits inside `sandbox/diameter-analysis/`.
- Follow project rule: no “back-compat defaults” unless explicitly requested.

---

## Part A — Console logging format

### Implementation
0. **Move logging setup to shared location:**
   - Move `sandbox/diameter-analysis/gui/logging_setup.py` → `sandbox/diameter-analysis/logging_setup.py`.
   - Update all imports to use the new shared module (e.g., `from logging_setup import configure_logging` or relative import as appropriate).
   - Ensure no other modules import from the old GUI path after this change.

1. Find the logging configuration function used by the GUI run path (likely `configure_logging(...)`).
   - Update the **console handler formatter** to:

```python
console_fmt = "[%(levelname)s] %(name)s:%(funcName)s:%(lineno)d: %(message)s"
```

2. Ensure the console handler does **not** prepend timestamps (leave timestamps for file logging if you have a file handler).

### Acceptance criteria
- Running `uv run python run_gui.py` produces console logs like:
  - `[INFO] gui.controllers:detect:123: Detect started`
- No timestamps appear in console output (unless you explicitly want them and document it in the ticket).

---

## Part B — Diameter plot trace label includes roi/channel

### Implementation
1. Identify where the diameter Plotly dict is created (commonly a helper like `make_diameter_figure_dict(...)`).
2. Update the trace `name` (or `legendgroup`/`hovertemplate` if preferred) to include:
   - `roi_id=<id>, ch=<id>`
3. The roi/channel values must come from the **actual analyzed result** (not defaults).
   - If `DiameterResult` (or your bundle) carries these fields, use them directly.
   - If multiple traces exist (e.g., raw vs filtered), include roi/channel consistently.

### Acceptance criteria
- After selecting a file and clicking Detect, the diameter trace legend shows something like:
  - `Diameter (roi 1, ch 1)`
- Works for synthetic mode too (choose a consistent label, e.g., `Synthetic` or `roi/ch N/A`).

---

## Tests
- If you have unit tests for plot dict creation, add/extend one to assert the trace name includes roi/channel when present.
- Logging format change does not require tests.

## Suggested files (confirm in repo)
- `sandbox/diameter-analysis/logging_setup.py` (new shared location for `configure_logging`)
- Any modules importing `configure_logging` (search in repo for `configure_logging\(` and `logging_setup`)
- `sandbox/diameter-analysis/gui/plotting.py` (or figure construction module)
- Possibly `sandbox/diameter-analysis/gui/controllers.py` if it passes roi/channel into plotting helpers
