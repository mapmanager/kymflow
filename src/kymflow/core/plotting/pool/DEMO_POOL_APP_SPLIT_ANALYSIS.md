# demo_pool_app.py Split Analysis

**Implementation status:** Priority 1 (PoolControlPanel) and Priority 2 (PlotSelectionHandler) are implemented. Control panel lives in `pool_control_panel.py`; selection logic in `selection_handler.py`. `demo_pool_app.py` is reduced to orchestration (~735 lines).

## Summary

- **File:** `demo_pool_app.py` (~1430 lines)
- **Main content:** Single class `PlotController` (~1350 lines) + `main()` entrypoint (~45 lines)
- **Role of PlotController:** Orchestrates data (via `DataFrameProcessor`), figure generation (via `FigureGenerator`), UI construction, event handling, and **linked selection** (rect/lasso across multiple plots).

Existing separation already in place:
- **Data:** `DataFrameProcessor` (dataframe_processor.py)
- **Figures:** `FigureGenerator` (figure_generator.py)
- **State shape:** `PlotState` / `PlotType` (plot_state.py)
- **Helpers:** `plot_helpers.py` (numeric_columns, points_in_polygon, parse_plotly_path_to_xy, etc.)
- **Config:** `PoolPlotConfig` (pool_plot_config.py)

So the remaining bulk in `PlotController` is: **UI construction**, **state↔widget sync**, **event handling**, and **selection logic**.

---

## PlotController Method Map (by concern)

| Lines (approx) | Method / block | Concern |
|----------------|----------------|---------|
| 35–148 | `__init__` | Setup: df, data_processor, figure_generator, plot_states, layout, **all UI handle refs** (20+), selection state |
| 156–208 | `_state_to_widgets` | State → UI (populate widgets from PlotState) |
| 210–267 | `_widgets_to_state` | UI → State (read widgets into PlotState) |
| 273–311 | `build` | Top-level UI: header, splitter, control panel, plot container |
| 312–483 | `_build_control_panel` | **Left panel:** layout, plot radio, buttons, Pre Filter card, plot type, group/color, swarm, mean/std, X/Y aggrids |
| 484–537 | `_build_plot_options` | Plot options card (line widths, raw, point size, legend) |
| 538–622 | `_rebuild_plot_panel` | Create 1x1 / 1x2 / 2x1 / 2x2 plot grid, wire click/relayout |
| 623–721 | `_create_column_aggrid` | Single aggrid for column selection (X or Y) |
| 728–802 | `_on_splitter_change`, `_get_num_plots_for_layout`, `_on_plot_radio_change`, `_on_layout_change`, `_on_plot_selection_change` | Layout/plot-index events |
| 818–864 | `_apply_current_to_others`, `_save_config`, `_reset_to_default` | Apply state, save config, reset |
| 863–946 | `_on_x_column_selected`, `_on_y_column_selected`, `_on_any_change` | Column selection + **any control change** (validation, state update, replot) |
| 945–976 | `_is_selection_compatible`, `_update_selection_label`, `_clear_selection` | Selection helpers |
| 976–981 | `_on_open_csv` | Placeholder |
| 981–995 | `_on_keyboard_key` | Esc = clear selection; Cmd/Ctrl = extend selection |
| 997–1096 | `_on_plotly_relayout` | **Large:** parse rect/lasso from relayout payload, compute selected row_ids, extend/replace selection, apply to all plots |
| 1098–1150 | `select_points_by_row_id`, `_apply_selection_to_all_plots` | Programmatic selection + apply selection to plot figures |
| 1151–1184 | `_sync_controls` | Enable/disable controls by plot type |
| 1185–1239 | `_on_plotly_click` | Click → row_id or group summary, update clicked label |
| 1241–1336 | `_compute_selected_points_from_range`, `_compute_selected_points_from_lasso` | **Selection geometry:** box select and lasso (point-in-polygon) |
| 1292–1379 | `_replot_current`, `_replot_all`, `_make_figure_dict` | Replot one/all, build figure dict (delegate to FigureGenerator) |

**Common patterns:**
1. **State ↔ widgets:** `_state_to_widgets` / `_widgets_to_state` — many widget refs and repetitive field mapping.
2. **Control panel as one big method:** ~250 lines of NiceGUI layout and widget creation in `_build_control_panel` + `_build_plot_options` + `_create_column_aggrid`.
3. **Selection pipeline:** keyboard (extend modifier) → relayout (rect/lasso) → compute row_ids → update `_selected_row_ids` → `_apply_selection_to_all_plots` → `_update_selection_label`. All live in the controller.
4. **Event handlers** that only update state and call one of: `_replot_current`, `_replot_all`, `_sync_controls`, `_state_to_widgets`, `_rebuild_plot_panel`.

---

## Prioritized Split (2–3 categories)

### Priority 1 — Control panel UI (new module)

**Goal:** Move all control-panel construction and state↔widget binding into one place so `PlotController` no longer owns 20+ widget refs and 250+ lines of UI code.

**Proposed new file:** `pool_control_panel.py` (or `control_panel.py` under `pool/`).

**Proposed class:** `PoolControlPanel` (or similar)

- **Responsibilities:**
  - Build the left panel (layout select, plot radio, buttons, Pre Filter card, plot type, group/color, swarm, mean/std, X/Y column aggrids, plot options card).
  - Hold references to all those widgets.
  - Provide:
    - `bind_state(state: PlotState)` → populate widgets from state.
    - `get_state() -> PlotState` → build PlotState from current widget values (equivalent to current `_widgets_to_state` but using panel’s own refs).
  - Optionally: `set_callbacks(on_change, on_x_selected, on_y_selected, ...)` so the panel doesn’t depend on `PlotController` directly.

- **What stays in PlotController:**
  - Creating the panel once (e.g. `self._control_panel = PoolControlPanel(...)` inside `_mainSplitter.before`).
  - Calling `_control_panel.bind_state(state)` / `_control_panel.get_state()` from `_state_to_widgets` / `_widgets_to_state` (which become thin wrappers or inlined).
  - `_sync_controls()` can move into the panel as `sync_controls(plot_type: PlotType)` if the panel holds the widget refs; PlotController then calls it with `plot_states[self.current_plot_index].plot_type`.

- **Benefits:**
  - Removes ~250 lines and 20+ widget attributes from PlotController.
  - Control panel can be tested or reused (e.g. different layout) without the rest of the app.
  - Single place for “which widgets exist” and “how state maps to/from widgets”.

**Boundary:** PlotController still owns `plot_states`, `current_plot_index`, and layout string; it passes the “current” PlotState into the panel and gets back a PlotState from `get_state()`. Column names (xcol/ycol) can stay in PlotState and be set by panel callbacks when user picks from aggrid.

---

### Priority 2 — Selection handling (new class, new or existing file)

**Goal:** Isolate all “linked selection” logic (rect/lasso, extend modifier, apply to plots, label update) so PlotController only delegates events and holds the list of plot widgets + plot_states.

**Proposed new file:** `selection_handler.py` (in `pool/`).

**Proposed class:** `PlotSelectionHandler` (or `LinkedSelectionHandler`)

- **Inputs (injected):**
  - `data_processor: DataFrameProcessor`
  - `figure_generator: FigureGenerator` (for `get_axis_x_for_selection`)
  - `row_id_col: str`
  - Callback to “apply selection to all plots”: e.g. `apply_to_plots(selected_row_ids: set[str])` that PlotController implements by calling `_make_figure_dict(state, selected_row_ids)` and `plot.update_figure(...)` for each compatible plot.
  - Optional callback to update a “selection count” label: `update_label(count: int)`.

- **State owned by handler:**
  - `selected_row_ids: set[str]`
  - `extend_selection_modifier: bool` (Cmd/Ctrl held).

- **Methods:**
  - `handle_relayout(payload: dict, plot_index: int, plot_state: PlotState)`  
    Parse rect/lasso from payload; compute row_ids (using data_processor + figure_generator + `_compute_selected_points_from_range` / `_compute_selected_points_from_lasso`); merge with existing if extend modifier; set `selected_row_ids`; call `apply_to_plots` and `update_label`.
  - `handle_clear()`  
    Clear `selected_row_ids`, call `apply_to_plots`, `update_label`.
  - `handle_key(key_name, keydown: bool)`  
    Escape → handle_clear(); Meta/Control → set extend modifier.
  - `select_by_row_id(row_id: str)`  
    Same logic as current `select_points_by_row_id` (find scatter plot, filter df, set selected_row_ids, apply, update label).
  - `get_selected_row_ids() -> set[str]`  
    So PlotController can pass them into `_make_figure_dict`.

- **Moved from PlotController:**
  - `_compute_selected_points_from_range`, `_compute_selected_points_from_lasso` (either as methods of the handler or as module-level functions in `selection_handler.py` using `plot_helpers.points_in_polygon` and figure_generator’s axis helper).
  - The bulk of `_on_plotly_relayout` (parsing + call into handler).
  - `_clear_selection`, `_on_keyboard_key`, `select_points_by_row_id`, `_apply_selection_to_all_plots`, `_update_selection_label` (controller keeps a thin wrapper that delegates to handler and/or updates its own `_selection_label` via callback).

- **PlotController retains:**
  - The list `_plots` and `plot_states`; the “apply selection to all plots” implementation (loop over plots, `_make_figure_dict(..., selected_row_ids)`, `update_figure`).
  - Wiring: relayout event → `selection_handler.handle_relayout(...)`; keyboard → `selection_handler.handle_key(...)`; Clear button → `selection_handler.handle_clear()`.

**Benefits:**
  - Selection logic (~250 lines) lives in one place; easier to test (e.g. payload → row_ids) and to change (e.g. different selection modes).
  - PlotController no longer mixes selection parsing with layout and control logic.

**Optional:** Keep `_is_selection_compatible(plot_type)` in PlotController or move to `plot_helpers` / selection_handler; it’s a one-liner and used when wiring relayout and when applying to plots.

---

### Priority 3 — Event orchestration and plot layout (keep in controller, optional small helpers)

**Goal:** Keep PlotController as a thin orchestrator: it owns `plot_states`, layout, and plot widget list; it delegates to Control Panel, SelectionHandler, DataFrameProcessor, and FigureGenerator. No new file is strictly required; optional: extract “layout → number of plots” and “layout string → grid structure” into a tiny helper if you want to reuse layout logic elsewhere.

**What remains in PlotController (after Priority 1 and 2):**

- **Initialization:** Build `DataFrameProcessor`, `FigureGenerator`, load config, create `plot_states`, create `PoolControlPanel`, create `PlotSelectionHandler` with callback that uses `_make_figure_dict` + `_plots[i].update_figure`.
- **build():** Header, splitter, `_control_panel.build(...)` in `before`, plot container in `after`, `_rebuild_plot_panel()`.
- **Layout/plot index:** `_rebuild_plot_panel`, `_on_layout_change`, `_on_plot_radio_change`, `_on_plot_selection_change`, `_get_num_plots_for_layout` — all stay; they’re short and central to “which plot is active” and “how many plots”.
- **State sync:** `_state_to_widgets` / `_widgets_to_state` become thin (panel.bind_state / panel.get_state) or inlined where used.
- **Control events:** `_on_any_change` (validate, update plot_states, replot, sync_controls) — can stay; optionally move validation (e.g. “group required for box/violin”) into a small `validate_plot_state(state, df) -> PlotState` in `plot_helpers` or `plot_state.py`.
- **Replot:** `_replot_current`, `_replot_all`, `_make_figure_dict` — stay; they’re the glue between state, FigureGenerator, and UI.
- **Click:** `_on_plotly_click` can stay (it’s mostly “get row_id from point, show in label”); or move “click → row_id / group summary” into a tiny helper used by controller.

**Optional helper module:** `layout_helpers.py` with e.g. `get_num_plots_for_layout(layout_str: str) -> int` and, if desired, `layout_grid_dimensions(layout_str: str) -> tuple[int, int]` so both the controller and any future layout UI can use the same logic.

---

## Suggested order of implementation

1. **Priority 1 — Control panel**  
   Add `pool_control_panel.py` and `PoolControlPanel`; move widget creation and state↔widget logic; replace PlotController’s widget refs and `_build_control_panel` / `_build_plot_options` / `_create_column_aggrid` with panel construction and delegation. Verify UI and replot behavior unchanged.

2. **Priority 2 — Selection handler**  
   Add `selection_handler.py` and `PlotSelectionHandler`; move selection state, rect/lasso computation, relayout parsing, clear/keyboard, and “apply to plots”; wire PlotController to call the handler. Verify rect/lasso, extend selection, and clear selection still work.

3. **Priority 3 — Optional cleanup**  
   Extract `_get_num_plots_for_layout` (and optionally layout dimensions) to a small helper if useful; optionally extract `_on_any_change` validation into a `validate_plot_state` helper. Leave the rest in PlotController as orchestration.

After 1 and 2, `demo_pool_app.py` should shrink to roughly: ~200–350 lines of PlotController (init, build, layout/plot-index events, replot, click, thin delegation to panel and selection handler) + `main()`. The control panel and selection handler become reusable and testable on their own.
