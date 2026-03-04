# Ticket 023 — GUI: Auto-reset Plotly axes to full extent on new selection/load

## Goal
When a **new kymograph is loaded** (from FileTableView selection or “Generate synthetic”), reset Plotly view to the **full x/y extent** of the newly loaded data **before** any user zooming.

This prevents “sticky zoom” from a previous file making the new file appear blank/zoomed-in incorrectly.

## Scope
- **Edit only** `sandbox/diameter-analysis/` (do **not** modify anything under `kymflow/`).
- Keep the established boundary:
  - Only `gui/diameter_kymflow_adapter.py` may import `kymflow.core.api.kym_external`.
- Keep behavior of `plotly_relayout` x-sync from Ticket 021 intact.

## Desired behavior
1. **On new file selection** (FileTableView → controller.load_selected_path → controller.load_real_kym):
   - Image heatmap plot shows the full kymograph (x and y reset).
   - Diameter plot shows full time range (x reset), and y range auto (or reset) for that series.
2. **On “Generate synthetic”**:
   - Same: both plots reset to full extent for synthetic.
3. This should happen **only on new dataset load**, not on every state update.
4. It must not fight the user:
   - If the user zooms after load, keep their zoom.
   - Only “fresh load” triggers full reset.

## Implementation notes (recommended)
- Add a small controller flag or “generation id” (e.g., `state.data_version: int`) incremented whenever a new dataset is loaded:
  - increment in `generate_synthetic()` and `load_real_kym()` (or `load_selected_path()` right after successful load).
- In controller figure rebuild path (`_rebuild_figures()` or equivalent), when it detects `data_version` changed since last rebuild:
  - Set full ranges explicitly in `fig_img["layout"]["xaxis"]["range"]` and `fig_img["layout"]["yaxis"]["range"]`.
  - Set `fig_line["layout"]["xaxis"]["range"]` to full time range.
  - Do **not** set these ranges on subsequent rebuilds if version unchanged.
- Full extents:
  - Image plot:
    - x range: [0, num_time_lines-1] or physical time depending on how plotting is currently done. Use whatever x-axis units the plot uses today.
    - y range: [0, num_space_px-1] (or physical distance) consistent with current heatmap.
  - Line plot:
    - x range: [min(time), max(time)] or [0, duration] consistent with existing.
- Ensure the relayout sync logic still works: after reset, both plots should be aligned on x.

## Acceptance criteria
- Running GUI:
  - Start app → select file A → zoom somewhere → select file B → plots show full extents of B (not stuck at A’s zoom).
  - Generate synthetic → zoom → generate synthetic again → full reset.
- No new test failures; existing boundary tests still pass.

## Tests
Add unit tests focused on controller behavior (no browser automation needed):
- A test that calls controller load method twice and verifies that after second load, `controller.fig_img["layout"]["xaxis"]["range"]` (and y range) correspond to new dataset’s extents.
- A test that simulates a user zoom by calling `controller.on_relayout(...)` to set an x range, then calls a non-load state update (e.g., toggling overlays) and confirms the range is preserved.
- A test that new dataset load overwrites the previous zoom range (i.e., reset happens only on load).

## Files likely touched
- `sandbox/diameter-analysis/gui/controllers.py`
- Possibly `sandbox/diameter-analysis/gui/plotting.py` (only if easiest to centralize “compute full extents” helpers)
- `sandbox/diameter-analysis/tests/` (new/updated tests)

## Out of scope
- Any changes to kymflow.
- Any redesign of plotly x-sync; just ensure reset integrates with the current sync implementation.
