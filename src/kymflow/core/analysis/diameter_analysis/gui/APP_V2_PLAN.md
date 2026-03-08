# Plan: app_v2.py — Refactor diameter_analysis GUI to Use ImageRoiWidget and LinePlotWidget

**Date:** 2025-03-08  
**Source (read-only):** `kymflow/src/kymflow/core/analysis/diameter_analysis/gui/app.py`, `views.py`, `controllers.py`, `plotting.py`, `models.py`  
**Target (new code):** `kymflow/src/kymflow/core/analysis/diameter_analysis/gui/app_v2.py`  
**Nicewidgets source:** `nicewidgets/src/nicewidgets/image_line_widget/`

---

## 1. Current App Structure and Flow (Read From)

### 1.1 Entry Point: `app.py` (lines 1–94)

- **`_make_default_state() -> AppState`** (lines 21–71): Builds `AppState` with `synthetic_params`, `detection_params`, `post_filter_params`. Imports `SyntheticKymographParams`, `DiameterDetectionParams`, `DiameterMethod`, and `PostFilterParams` from `synthetic_kymograph` and `diameter_analysis`.
- **`home()`** (lines 74–80): `@ui.page("/")` — creates `AppState`, `AppController(state)`, calls `controller.initialize_kym_list(SEED_FOLDER)`, `controller._rebuild_figures()`, then `build_home_page(controller)`.
- **`main()`** (lines 83–89): Configures logging, runs `ui.run`.
- **Imports:** `config.SEED_FOLDER`, `models.AppState`, `controllers.AppController`, `views.build_home_page`, `logging_setup.configure_logging`, `synthetic_kymograph.SyntheticKymographParams`, `diameter_analysis.DiameterDetectionParams`, `diameter_analysis.DiameterMethod`.

### 1.2 Architecture Overview

```
app.py
  └── home() → AppController(state) → build_home_page(controller)
        │
        ├── AppController (controllers.py)
        │     ├── state: AppState
        │     ├── fig_img: dict | None   (plotly figure for kymograph)
        │     ├── fig_line: dict | None  (plotly figure for diameter)
        │     ├── _rebuild_figures() uses:
        │     │     - plotting.make_kymograph_figure_dict()
        │     │     - plotting.overlay_edges_on_kymograph_dict()
        │     │     - plotting.make_diameter_figure_dict()
        │     ├── on_relayout(source, relayout) for x-axis sync
        │     └── set_img(), load_real_kym(), generate_synthetic(), detect(), etc.
        │
        └── build_home_page (views.py)
              ├── FileTableView (from kymflow.gui_v2)
              ├── Buttons: Generate synthetic, Detect, Save, Show center
              ├── Splitter: left = params cards, right = params + fig_img + fig_line
              └── fig_img_el = ui.plotly(controller.fig_img)
                  fig_line_el = ui.plotly(controller.fig_line)
                  on plotly_relayout → controller.on_relayout()
```

### 1.3 Key Data Flow

1. **Image loading:** `FileTableView` selection → `controller.load_selected_path(path)` → `load_real_kym(kym)` → `set_img(...)` → `_rebuild_figures()`.
2. **Synthetic:** `Generate synthetic` → `controller.generate_synthetic()` → `set_img(...)` → `_rebuild_figures()`.
3. **Detection:** `Detect` → `controller.detect()` → updates `state.results` → `_rebuild_figures()`.
4. **Plot refresh:** `controller._on_state_change` set by `build_home_page`; `_refresh()` assigns `controller.fig_img` / `controller.fig_line` to `fig_img_el.figure` / `fig_line_el.figure` and calls `update()`.
5. **X-axis sync:** User zoom/pan on either plot → `plotly_relayout` → `controller.on_relayout(source, e.args)` → parses x range or autorange reset → applies to both `fig_img` and `fig_line` via `set_xrange()` → `_emit()` → `_refresh()` updates both plot elements.

### 1.4 Plotting Module (plotting.py)

- **`make_kymograph_figure_dict(img, seconds_per_line, um_per_pixel, title)`** — returns plotly dict with heatmap; x = time (s), y = space (um).
- **`overlay_edges_on_kymograph_dict(fig, seconds, left_um, right_um, center_um)`** — appends scatter traces for left/right/center edges.
- **`make_diameter_figure_dict(results, seconds_per_line, um_per_pixel, post_filter_params, title)`** — returns plotly dict with diameter vs time (and optional filtered trace).
- **`set_xrange(fig, x0, x1)`** — sets layout xaxis range.

---

## 2. Nicewidgets ImageRoiWidget and LinePlotWidget API (Read From)

### 2.1 ImageRoiWidget (`image_roi_widget.py`)

| API | Purpose |
|-----|---------|
| `__init__(widget_name, manager, config?, initial_rois?, on_roi_event?, on_axis_change?)` | Manager is `ChannelManager`; ROIs are `RegionOfInterest`. |
| `set_file(new_manager, new_rois?)` | Replace image data and optional ROIs. Rebuilds plot. |
| `add_line(x, y, name, x_label?, y_label?, config?)` | Overlay line on heatmap. |
| `update_line(name, x, y, ...)` | Update existing line. |
| `delete_line(name)`, `clear_lines()` | Remove line(s). |
| `set_x_axis_range(x_range)`, `set_x_axis_autorange()`, `set_y_axis_autorange()` | Programmatic axis control. |
| `set_toolbar_visible(visible)` | Show/hide toolbar. |
| `select_roi_by_name(name, emit_select=?)` | Select ROI by name. |

**ChannelManager** (models.py): `channels: List[Channel]`, `row_scale`, `col_scale`, `x_label`, `y_label`, `active_channel_name`.  
**Channel**: `name`, `data` (np.ndarray), `colorscale`.  
**RegionOfInterest**: `name`, `r0`, `r1`, `c0`, `c1` — rows = dim 0, cols = dim 1.  
**AxisEvent**: `widget_name`, `type`, `x_range`, `y_range`.

### 2.2 LinePlotWidget (`line_plot_widget.py`)

| API | Purpose |
|-----|---------|
| `__init__(widget_name, x?, y?, name?, x_label?, y_label?, cfg?, on_axis_change?)` | Seed line optional; `(x,y,name)` all or none. |
| `add_line(x, y, name, x_label?, y_label?, config?, y_axis?)` | Add line. |
| `update_line(name, x, y, ...)`, `delete_line(name)`, `clear_lines()` | Line CRUD. |
| `set_x_axis_range(x_range)`, `set_x_axis_autorange()`, `set_y_axis_autorange()`, `set_y_axis_range(y_range)` | Programmatic axis control. |
| `acq_image_events` | `AcqImageEventManager` for event rects (optional). |

---

## 3. Data Mapping: diameter_analysis → nicewidgets

| diameter_analysis | nicewidgets |
|-------------------|-------------|
| `img` (n_time, n_space), seconds_per_line, um_per_pixel | `ChannelManager([Channel("Kymograph", img)], row_scale=seconds_per_line, col_scale=um_per_pixel, x_label="time (s)", y_label="space (um)")` |
| Full-image ROI (0..n_time, 0..n_space) | `RegionOfInterest("Full", 0, n_time-1, 0, n_space-1)` — single ROI for full extent |
| Edge overlays (left_um, right_um, center_um) | `add_line(seconds, left_um, "left")`, etc. on ImageRoiWidget |
| Diameter trace (t, d_um) | `LinePlotWidget.add_line(t, d_um, "Diameter", ...)` |
| Post-filtered diameter | `add_line(t, d_filtered, "Diameter filtered", ...)` |

---

## 4. Decisions (Resolved)

| # | Question | Decision |
|---|----------|----------|
| 1 | ROI usage | ImageRoiWidget toolbar **visible**; single **full-extent ROI**. |
| 2 | Controller | **AppControllerV2** that owns widgets. |
| 3 | Shared code | Separate v2 module: **controllers_v2.py**, **views_v2.py**. |
| 4 | AcqImageEvent | **Omit** in app_v2. |
| 5 | FileTableView | **Same** FileTableView and file-selection flow (kymflow.gui_v2). |
| 6 | Run entry | `python -m kymflow.core.analysis.diameter_analysis.gui.app_v2` — no CLI flags, no existing launcher. |

---

## 5. Implementation Plan

### 5.1 Confirmed Approach

- ImageRoiWidget: toolbar visible, single full-extent ROI.
- AppControllerV2: owns ImageRoiWidget and LinePlotWidget, drives them via their APIs.
- Separate v2 files: `controllers_v2.py`, `views_v2.py`.
- Omit AcqImageEvent.
- Reuse FileTableView and gui_v2 flow.

### 5.2 New File: `app_v2.py`

**Location:** `kymflow/src/kymflow/core/analysis/diameter_analysis/gui/app_v2.py`

**Responsibilities:**

1. Imports from `controllers_v2`, `views_v2`, config, models, etc.
2. Defines `_make_default_state()` (copy/reuse from app.py).
3. Defines `home_v2()` as `@ui.page("/")` that creates state, `AppControllerV2(state)`, initializes kym list, calls `build_home_page_v2(controller)`.
4. Defines `main()` and `if __name__` to run via `python -m kymflow.core.analysis.diameter_analysis.gui.app_v2`.

### 5.3 New Controller: `controllers_v2.py`

**Location:** `kymflow/src/kymflow/core/analysis/diameter_analysis/gui/controllers_v2.py`

**Responsibilities:**

1. Hold references to `ImageRoiWidget` and `LinePlotWidget` (or receive them from the view and wire callbacks).
2. On `set_img`, `load_real_kym`, `generate_synthetic`:
   - Build `ChannelManager` from `img`, `seconds_per_line`, `um_per_pixel`.
   - Build full-extent `RegionOfInterest`.
   - Call `image_roi_widget.set_file(manager, [roi])`.
   - Optionally add edge overlays via `add_line` / `update_line` / `clear_lines`.
3. On `detect`, `apply_post_filter_only`:
   - Extract `t`, `d_um`, `d_filtered` from `state.results` (reuse `plotting._extract_*`).
   - Call `line_plot_widget.clear_lines()` then `add_line` for raw and filtered.
4. X-axis sync:
   - Implement `on_axis_change(ev: AxisEvent)` that:
     - If `ev.widget_name == "kymograph"`: call `line_plot_widget.set_x_axis_range(ev.x_range)` or `set_x_axis_autorange()`.
     - If `ev.widget_name == "diameter"`: call `image_roi_widget.set_x_axis_range(ev.x_range)` or `set_x_axis_autorange()`.
5. Reuse `plotting` helpers (`_extract_diameter_um`, `_extract_time_s`, `_extract_filtered_diameter_um`, `apply_post_filter_1d`) for data extraction.

### 5.4 View: `build_home_page_v2` in `views_v2.py`

**Location:** `kymflow/src/kymflow/core/analysis/diameter_analysis/gui/views_v2.py`

Decision #3 (separate v2 module) implies **Option B**: `build_home_page_v2` lives in `views_v2.py`. Your answers are sufficient — the view will mirror `views.build_home_page` (FileTableView, buttons, splitter, params cards) but replace the raw `ui.plotly` blocks with:

```python
# Replace fig_img_el / fig_line_el (views.py 164-169) with:
manager = controller._state_to_channel_manager()
roi = controller._full_extent_roi()
image_roi_widget = ImageRoiWidget(
    widget_name="kymograph",
    manager=manager,
    initial_rois=[roi],
    on_axis_change=controller.on_axis_change,
)
line_plot_widget = LinePlotWidget(
    widget_name="diameter",
    x_label="time (s)", y_label="diameter (um)",
    on_axis_change=controller.on_axis_change,
)
controller.register_widgets(image_roi_widget, line_plot_widget)
controller.populate_widgets()
```

Adapter helpers (`_state_to_channel_manager`, `_full_extent_roi`) live in `AppControllerV2`. Handle initial no-image case: either render placeholder (e.g. empty plot) or defer widget creation until first image load.

### 5.5 Helpers (in AppControllerV2)

`_state_to_channel_manager()` and `_full_extent_roi()` live in `controllers_v2.py`. The former uses `self.resolve_units(source=self.state.source)` (same pattern as existing AppController).

### 5.6 Edge Overlays on ImageRoiWidget

On `_rebuild_figures` (or equivalent in v2):

1. `image_roi_widget.clear_lines()` to remove old overlays.
2. Call `controller._extract_overlays_um()` to get `seconds`, `left_um`, `right_um`, `center_um`.
3. If `state.gui.show_center_overlay` is False, set `center_um = None`.
4. Call `image_roi_widget.add_line(seconds, left_um, "left", config=LineConfig(...))` etc. for each non-None overlay.

---

## 6. Proposed nicewidgets Updates (Propose in Plan)

To make integration clearer and less error-prone for external callers (e.g. app_v2):

### 6.1 API documentation

1. **Add `INTEGRATION.md`** in `nicewidgets/src/nicewidgets/image_line_widget/` with:
   - Quick start: minimal ImageRoiWidget and LinePlotWidget setup.
   - Data mapping: numpy img shape (rows, cols) → ChannelManager (row_scale, col_scale), ROI (r0,r1,c0,c1).
   - Axis linking: wiring `on_axis_change` between widgets.
   - `set_file` usage for swapping image context.

2. **Expand docstrings** in `ImageRoiWidget` and `LinePlotWidget` with an "Integration" section describing:
   - Required vs optional constructor args.
   - Order of operations (e.g. `set_file` then `add_line`).
   - Units: `row_scale` = x-axis units per row index, `col_scale` = y-axis units per column index.

### 6.2 Optional API clarifications

1. **`ImageRoiWidget.set_file` with empty ROIs:** When `new_rois` is `None`, the widget clears ROIs. Document that a single full-extent ROI can be passed for "whole image" display.

2. **`LinePlotWidget` empty init:** Document that `(x, y, name)` can all be `None` for an empty plot; call `add_line` afterward.

3. **`update` vs `update_figure`:** ImageRoiWidget uses `self.plot.update_figure(self.plot_dict)` in some paths; LinePlotWidget uses `self.plot.update()`. Ensure consistency and document which to use if a caller needs to trigger a manual refresh.

4. **Factory helper (optional):** Add `create_channel_manager_from_kymograph(img, seconds_per_line, um_per_pixel) -> ChannelManager` in nicewidgets to reduce boilerplate for kymograph-style apps. (Low priority.)

---

## 7. Exact Files to Read vs Write

| Action | Path |
|--------|------|
| READ | `kymflow/.../gui/app.py` |
| READ | `kymflow/.../gui/views.py` |
| READ | `kymflow/.../gui/controllers.py` |
| READ | `kymflow/.../gui/plotting.py` |
| READ | `kymflow/.../gui/models.py` |
| READ | `kymflow/.../gui/config.py` |
| READ | `kymflow/.../gui/widgets.py` |
| READ | `nicewidgets/.../image_line_widget/image_roi_widget.py` |
| READ | `nicewidgets/.../image_line_widget/line_plot_widget.py` |
| READ | `nicewidgets/.../image_line_widget/models.py` |
| READ | `nicewidgets/.../image_line_widget/image_roi_widget_demo_app.py` |
| WRITE | `kymflow/.../gui/app_v2.py` |
| WRITE | `kymflow/.../gui/controllers_v2.py` |
| WRITE | `kymflow/.../gui/views_v2.py` |
| PROPOSE | `nicewidgets/.../image_line_widget/INTEGRATION.md` |
| PROPOSE | Docstring updates in `image_roi_widget.py`, `line_plot_widget.py` |

---

## 8. Implementation Order

1. Create `controllers_v2.py` with `AppControllerV2` (extend or delegate to existing controller logic for set_img, load_real_kym, detect, etc.), widget refs, `register_widgets`, `populate_widgets`, `on_axis_change`, `_state_to_channel_manager`, `_full_extent_roi`.
2. Create `views_v2.py` with `build_home_page_v2` (FileTableView, buttons, splitter, params cards, ImageRoiWidget, LinePlotWidget).
3. Create `app_v2.py` with `_make_default_state`, `home_v2`, `main`, `if __name__`. Entry: `python -m kymflow.core.analysis.diameter_analysis.gui.app_v2`.
4. Implement edge overlay logic (add_line for left/right/center) and diameter trace logic in controller.
5. Add nicewidgets `INTEGRATION.md` and docstring improvements (optional).
6. Manual test: load file, generate synthetic, detect, verify axis linking and overlays.

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| ROI semantics mismatch (r0,r1 vs time, c0,c1 vs space) | Document in INTEGRATION.md; diameter_analysis uses (time, space) = (rows, cols). |
| AxisEvent thread safety | NiceGUI handles UI callbacks; ensure controller does not block. |
| Plot update timing | Use `set_file` / `add_line` / `update_line` in correct order; call `update()` / `update_figure()` as per widget API. |
| Import paths for synthetic_kymograph, diameter_analysis, logging_setup | Preserve same import structure as app.py (workspace/sandbox PYTHONPATH). |
