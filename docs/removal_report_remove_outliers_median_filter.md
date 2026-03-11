# Removal Report: Remove Outliers and Median Filter Checkboxes

## Summary

Removed the "Remove outliers (flow analysis)" and "Median filter" checkboxes from the Plotting tab (drawer) and all associated wiring. The line plot now always displays unfiltered data (remove_outliers=False, median_filter=0).

## Files Modified

### 1. `kymflow/gui_v2/views/line_plot_controls_view.py`
- **Removed**: `OnFilterChange` type alias
- **Removed**: `on_filter_change` constructor parameter and `_on_filter_change` attribute
- **Removed**: `_remove_outliers_cb` and `_median_filter_cb` checkbox attributes
- **Removed**: Both checkbox UI elements and their `_on_filter_change_handler` bindings
- **Removed**: `_on_filter_change_handler` method
- **Removed**: References to checkboxes in `_update_control_states`
- **Kept**: Full zoom button and `on_full_zoom` callback

### 2. `kymflow/gui_v2/pages/home_page.py`
- **Removed**: `_on_drawer_filter_change` method
- **Removed**: `on_filter_change=self._on_drawer_filter_change` from `LinePlotControlsView` constructor

### 3. `kymflow/gui_v2/views/image_line_viewer_v2_view.py`
- **Removed**: `_remove_outliers` and `_median_filter` instance attributes
- **Removed**: `apply_filters(remove_outliers, median_filter)` method
- **Changed**: `_update_line_for_current_roi` now always calls `get_analysis_value(..., remove_outliers=False, median_filter=0)`

### 4. `kymflow/tests/gui_v2/test_home_page_widgets.py`
- **Removed**: `test_home_page_drawer_filter_change_calls_apply_filters`

### 5. `kymflow/tests/gui_v2/test_image_line_viewer_v2_view.py`
- **Removed**: `test_apply_filters_stores_state_and_refreshes`
- **Removed**: `test_apply_filters_clear_both`
- **Updated**: Module docstring (removed apply_filters reference)

## Files NOT Modified (core analysis APIs unchanged)

The following modules still contain `remove_outliers` and `median_filter` parameters. They are used by other callers (e.g., `event_analysis_controller`, diameter analysis) and were not removed:

- `kymflow/core/image_loaders/kym_analysis.py` – `get_analysis_value(remove_outliers, median_filter)`
- `kymflow/core/plotting/line_plots.py` – plotting functions
- `kymflow/core/plotting/stall_plots.py` – stall plot functions
- `kymflow/gui_v2/views/image_line_viewer_view.py` – legacy view (has its own checkboxes)

## Verification

- All 43 relevant gui_v2 tests pass.
- Runtime: Line plot in the drawer shows velocity data without user-togglable filtering. Full zoom button still works.
