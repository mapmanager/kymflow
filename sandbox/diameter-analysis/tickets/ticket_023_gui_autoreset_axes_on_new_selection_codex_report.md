# ticket_023_gui_autoreset_axes_on_new_selection_codex_report

## Final report path
- `kymflow/sandbox/diameter-analysis/tickets/ticket_023_gui_autoreset_axes_on_new_selection_codex_report.md`

## Summary of what changed
- Added load-version tracking so plot axes reset to full extents only when a new dataset is loaded.
- Reset logic now applies full image x/y ranges and full line-plot x range on fresh loads.
- Preserved post-load user zoom behavior by keeping existing relayout x-sync flow unchanged.
- Added controller unit tests for: load-reset behavior, non-load rebuild preserving user zoom, and new-load overriding prior zoom.

## Modified code files
- `kymflow/sandbox/diameter-analysis/gui/controllers.py`
- `kymflow/sandbox/diameter-analysis/gui/models.py`
- `kymflow/sandbox/diameter-analysis/tests/test_controller_autoreset_axes_on_load.py`

## Artifacts created
- `kymflow/sandbox/diameter-analysis/tickets/ticket_023_gui_autoreset_axes_on_new_selection_codex_report.md`

## Unified diff (short)
### `gui/models.py`
```diff
@@
 class AppState:
@@
     x_range: Optional[tuple[float, float]] = None  # seconds
+    data_version: int = 0
     _syncing_axes: bool = False
```

### `gui/controllers.py`
```diff
@@ class AppController.__init__
         self.fig_img: Optional[dict] = None
         self.fig_line: Optional[dict] = None
+        self._last_built_data_version: int = -1
@@ def set_img(...)
         self.state.tiff_error = None
         self.state.results = None
+        self.state.x_range = None
+        self.state.data_version += 1
         self._rebuild_figures()
         self._emit()
@@ def _rebuild_figures(self) -> None:
+        is_fresh_load = self.state.data_version != self._last_built_data_version
@@
+        if is_fresh_load and self.fig_img and self.fig_line:
+            n_time, n_space = self.state.img.shape
+            max_x = float(max(0, n_time - 1) * seconds_per_line)
+            max_y = float(max(0, n_space - 1) * um_per_pixel)
+            full_x_range = (0.0, max_x)
+            self.state.x_range = full_x_range
+            img_layout = self.fig_img.setdefault("layout", {})
+            img_xaxis = img_layout.setdefault("xaxis", {})
+            img_yaxis = img_layout.setdefault("yaxis", {})
+            img_xaxis["range"] = [full_x_range[0], full_x_range[1]]
+            img_yaxis["range"] = [0.0, max_y]
+            line_layout = self.fig_line.setdefault("layout", {})
+            line_xaxis = line_layout.setdefault("xaxis", {})
+            line_xaxis["range"] = [full_x_range[0], full_x_range[1]]
@@
+        self._last_built_data_version = self.state.data_version
```

### `tests/test_controller_autoreset_axes_on_load.py`
```diff
+def test_load_twice_resets_to_new_full_extents() -> None:
+    ...
+
+def test_user_zoom_persists_on_non_load_rebuild() -> None:
+    ...
+
+def test_new_load_overwrites_previous_zoom_once() -> None:
+    ...
```

## Search confirmation
- Searched for:
  - `data_version`
  - `set_img(`
  - `on_relayout(`
  - `set_xrange(`
- Outcome:
  - Implemented version/reset logic in `gui/controllers.py` and `gui/models.py` only.
  - Added focused tests in `tests/test_controller_autoreset_axes_on_load.py`.
  - Did not modify `gui/views.py`, `gui/file_picker.py`, or any files under `kymflow/`.

## Validation commands run + results
Ran from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- Result: PASS (`54 passed, 1 warning`)

## Assumptions made
- `set_img(...)` is treated as the canonical “new dataset load” entry point (used by real/synthetic/tiff load paths), so incrementing `data_version` there satisfies the ticket’s “fresh load only” condition.
- Full extents should match existing axis units (seconds for x, microns for y), using `[0, (n-1)*scale]`.

## Risks / limitations / next steps
- This reset strategy assumes all new dataset loads route through `set_img(...)`; bypassing it would skip reset.
- The line plot y-axis is left to Plotly autorange, as requested.
- Manual GUI smoke test (A→zoom→B, synthetic regenerate) was not run in this ticket; behavior is covered via controller unit tests.

## Self-critique
- Pros:
  - Minimal mechanical change, centered in controller/state.
  - Keeps Ticket 021 x-sync semantics intact.
  - Tests directly cover the three requested behaviors.
- Cons:
  - `data_version` is controller-state coupling; future loaders must continue using `set_img(...)`.
- Drift risk/red flags:
  - If axis units change in plotting, reset extents must be kept consistent.
- What I would do differently next:
  - Add a small helper that computes full extents in one place for reuse by controller/tests.

## Required confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
