# ticket_021_plotly_xaxis_sync_and_controller_tests

## Goal
Finish and lock down Plotly **x-axis** sync between the kymograph heatmap plot and the diameter line plot, **without** syncing y-axis, and add targeted unit tests for the critical controller logic.

This ticket is the carry-forward “x-sync smoke test not fully correct” from ticket_011.

## Scope
### A) Fix/finish x-axis sync behavior
Update `gui/controllers.py::AppController.on_relayout(...)` (and any helper it calls) so that:

1. **Zoom/drag on the image plot** updates only the **x-range** of the line plot (via `state.x_range` / figure rebuild).
2. **Zoom/drag on the line plot** updates only the **x-range** of the image plot.
3. **Do not** touch y-axis ranges (never set `yaxis.range[...]`, `yaxis.autorange`, etc).
4. Support the typical Plotly relayout payload variants:
   - `xaxis.range[0]` / `xaxis.range[1]`
   - `xaxis.range` list form
   - `xaxis.autorange` reset
   - (If present) `xaxis2.*` should be handled safely, but keep behavior limited to x-range only.
5. Prevent recursion/feedback loops using the existing `state._syncing_axes` guard.

### B) Add an x-sync “smoke test” at the controller level (pytest)
Add/extend tests that validate **controller behavior** without needing NiceGUI rendering:
- A relayout payload from image with x-range should update `state.x_range` and trigger rebuild/emit.
- A relayout payload from line should do the same.
- A relayout payload containing only y-axis keys must **not** update `state.x_range` and must not rebuild/emit.
- Autorange reset should set `state.x_range` back to `None` (or the designed reset behavior), and rebuild once.

If necessary, structure the controller to make testing easier:
- It’s OK to factor out parsing into a pure function like `_parse_xrange_from_relayout(relayout: dict) -> (new_range, autorange_reset)` in `gui/controllers.py`.
- Keep any changes minimal and localized.

## Acceptance Criteria
- Manual UI check:
  - Drag-zoom on image updates line x-window; drag-zoom on line updates image x-window.
  - Y zoom on image does not force line y changes; y zoom on line does not force image y changes.
  - Double-click autorange behaves sensibly (resets linked x-range).
- `uv run pytest` passes.
- No new direct imports of `kymflow.core.api.kym_external` outside `gui/diameter_kymflow_adapter.py` (boundary tests remain green).

## Notes / Constraints
- Controller-only kymflow rule still applies.
- Keep changes focused; do not refactor unrelated UI layout in this ticket.
