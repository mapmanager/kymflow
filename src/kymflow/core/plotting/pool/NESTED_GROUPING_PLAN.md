# Plan: Option B - Nested Categorization with Restructured Grouping

## Overview

Restructure the grouping system to support nested categorization:
- **`group_col`** (existing "Group/Color") → becomes the `x` parameter for plotly plots (x-axis categorical grouping)
- **`color_grouping`** (new field) → becomes the `color` parameter for plotly plots (nested grouping within each x category)

This enables patterns like `px.box(df, x="grandparent_folder", y="vel_mean", color="roi_id")` where:
- `x` = `group_col` (x-axis categories)
- `color` = `color_grouping` (nested grouping within each x category)

---

## Phase 1: Data Model Changes

### 1.1 Update PlotState (`plot_state.py`)

**Changes:**
- Add new field: `color_grouping: Optional[str] = None`
- Update `to_dict()` method to include `color_grouping` in serialization
- Update `from_dict()` method to deserialize `color_grouping` (with backward compatibility - defaults to None if missing)
- Update comment for `group_col`: clarify it's used for x-axis grouping (categorical) in box/violin/swarm; for color/grouping in scatter/histogram

**Code location:**
- `plot_state.py` lines ~37, ~60, ~94

---

## Phase 2: UI Changes

### 2.1 Add New UI Select Widget (`demo_pool_app.py`)

**Changes:**
- Add instance variable: `_color_grouping_select: Optional[ui.select] = None`
- Create new select widget in `_build_control_panel()`:
  - Label: "Group/Nesting" (or "Color Grouping")
  - Options: `["(none)"] + categorical_candidates(self.df)`
  - Position: After "Group/Color" select (around line ~315)
  - Callback: `on_change=self._on_any_change`
  - Initial value: `"(none)"` or from `state.color_grouping`

**Code location:**
- `demo_pool_app.py` ~line 99 (instance variables)
- `demo_pool_app.py` ~line 315 (widget creation)

### 2.2 Update State-to-Widgets Sync (`demo_pool_app.py`)

**Changes:**
- In `_state_to_widgets()`: sync `_color_grouping_select.value` from `state.color_grouping` (or "(none)" if None)
- Ensure widget exists before setting value (add assertion or check)

**Code location:**
- `demo_pool_app.py` ~line 116 (`_state_to_widgets` method)

### 2.3 Update Widgets-to-State (`demo_pool_app.py`)

**Changes:**
- In `_widgets_to_state()`: read `color_grouping` from `_color_grouping_select.value`
- Map "(none)" → `None`, otherwise use the selected column name

**Code location:**
- `demo_pool_app.py` ~line 168 (`_widgets_to_state` method)

### 2.4 Update Control Enable/Disable Logic (`demo_pool_app.py`)

**Changes:**
- In `_sync_controls()`: enable `_color_grouping_select` for plot types that support nested grouping:
  - BOX_PLOT, VIOLIN, SWARM (primary focus)
  - Optionally: HISTOGRAM, CUMULATIVE_HISTOGRAM (can defer)
- For box/violin/swarm: `group_col` becomes **required** (for x-axis), so ensure it's enabled
- Consider showing validation warning if `group_col` is "(none)" for box/violin/swarm

**Code location:**
- `demo_pool_app.py` ~line 832 (`_sync_controls` method)

---

## Phase 3: Plot Generation Changes - Box/Violin/Swarm

### 3.1 Update `_figure_box()` (`figure_generator.py`)

**Current behavior:**
- Uses `state.xcol` for x-axis (categorical)
- Creates multiple traces when `group_col` is set (one trace per group value)

**New behavior:**
- Use `state.group_col` for x-axis (instead of `state.xcol`)
- Use Plotly's native `color` parameter for nested grouping:
  - If `color_grouping` is set: `go.Box(x=group_col_values, y=y_values, color=color_grouping_values, ...)`
  - If `color_grouping` is None: `go.Box(x=group_col_values, y=y_values, ...)` (single trace, no color grouping)
- Update x-axis title: `xaxis_title=state.group_col` (instead of `state.xcol`)
- Update validation: require `group_col` to be categorical (already exists, but now it's the x-axis requirement)

**Code location:**
- `figure_generator.py` ~line 606 (`_figure_box` method)

**Example transformation:**
```python
# OLD:
x = df_f[state.xcol].astype(str)
for group_value, sub in tmp.groupby("g", sort=True):
    fig.add_trace(go.Box(x=sub["x"], y=sub["y"], name=str(group_value), ...))

# NEW:
x = df_f[state.group_col].astype(str)  # group_col is now x-axis
if state.color_grouping:
    # Use Plotly's color parameter for nested grouping
    fig.add_trace(go.Box(
        x=x, 
        y=y, 
        color=df_f[state.color_grouping].astype(str),
        ...
    ))
else:
    fig.add_trace(go.Box(x=x, y=y, ...))
```

### 3.2 Update `_figure_violin()` (`figure_generator.py`)

**Changes:**
- Same pattern as `_figure_box()`
- Use `group_col` for x-axis, `color_grouping` for color parameter

**Code location:**
- `figure_generator.py` ~line 656 (`_figure_violin` method)

### 3.3 Update `_figure_swarm()` (`figure_generator.py`)

**Changes:**
- More complex due to manual jitter implementation
- Use `group_col` for x-axis categorical positions (instead of `state.xcol`)
- Use `color_grouping` for trace separation/coloring
- Adjust jitter logic to handle nested grouping:
  - Jitter should be applied within each `(x_category, color_group)` combination
  - May need to group by both `group_col` and `color_grouping` for jitter calculation

**Code location:**
- `figure_generator.py` ~line 430 (`_figure_swarm` method)

**Considerations:**
- Swarm uses manual jitter with deterministic seeds per group
- With nested grouping, need to ensure jitter is unique per `(x_category, color_group)` pair
- May need to adjust seed calculation: `seed = hash(f"{x_cat}_{color_group}") % (2**31)`

### 3.4 Update Selection Axis Mapping (`figure_generator.py`)

**Changes:**
- In `get_axis_x_for_selection()`:
  - For BOX_PLOT/VIOLIN: use `state.group_col` instead of `state.xcol` for categorical mapping
  - For SWARM: same change
- Update `_scatter_axis_x()` if it's used by box/violin (check current implementation)

**Code location:**
- `figure_generator.py` ~line 118 (`get_axis_x_for_selection` method)
- `figure_generator.py` ~line 126 (`_scatter_axis_x` method)

---

## Phase 4: Plot Generation Changes - Histogram (Optional, Can Defer)

### 4.1 Update `_figure_histogram()` (`figure_generator.py`)

**Current behavior:**
- Uses `xcol` for histogram bins (numeric)
- Optional grouping by `group_col` (one trace per group)

**New behavior:**
- Keep using `xcol` for histogram bins (numeric) - this stays the same
- Add support for `group_col` as x-axis grouping (if categorical)
- Add support for `color_grouping` as color parameter
- Pattern: `go.Histogram(x=xcol_values, color=color_grouping_values, ...)` with grouping by `group_col` if set

**Code location:**
- `figure_generator.py` ~line 812 (`_figure_histogram` method)

**Note:** This phase can be deferred - focus on box/violin/swarm first.

### 4.2 Update `_figure_cumulative_histogram()` (`figure_generator.py`)

**Changes:**
- Similar pattern to histogram
- Keep `xcol` for cumulative distribution calculation
- Add `group_col` and `color_grouping` support

**Code location:**
- `figure_generator.py` ~line 738 (`_figure_cumulative_histogram` method)

---

## Phase 5: Scatter Plot Considerations

### 5.1 Decision Point

**Options:**
- **Option A:** Keep scatter using `xcol` for x-axis (supports numeric x) - **RECOMMENDED**
- **Option B:** Switch scatter to use `group_col` for x-axis (only if categorical)

**Recommendation:** Keep scatter using `xcol` for now because:
- Scatter plots commonly use numeric x-axis
- Switching to `group_col` would break numeric x-axis support
- Scatter can still use `color_grouping` for color if desired

**Code location:**
- `figure_generator.py` ~line 287 (`_figure_scatter` method)
- `figure_generator.py` ~line 315 (`_figure_split_scatter` method)

---

## Phase 6: Validation and Edge Cases

### 6.1 Validation Logic (`demo_pool_app.py`)

**Changes:**
- In `_on_any_change()`: add validation for box/violin/swarm:
  - Require `group_col` != "(none)" (it's now the x-axis, so it's required)
  - Require `group_col` to be categorical (use `is_categorical_column()`)
  - When `color_grouping` is set, ensure it's categorical
  - Show `ui.notify` warnings for invalid combinations

**Code location:**
- `demo_pool_app.py` ~line 643 (`_on_any_change` method)

**Example validation:**
```python
# Box/Violin require categorical group_col for x-axis
if new_state.plot_type in (PlotType.BOX_PLOT, PlotType.VIOLIN, PlotType.SWARM):
    if not new_state.group_col or new_state.group_col == "(none)":
        ui.notify("Box/Violin/Swarm plots require a Group/Color column for x-axis.", type="warning")
        # Revert group_col selection
    elif not is_categorical_column(self.df, new_state.group_col):
        ui.notify("Group/Color column must be categorical for Box/Violin/Swarm plots.", type="warning")
        # Revert group_col selection
```

### 6.2 Backward Compatibility

**Changes:**
- In `PlotState.from_dict()`: handle missing `color_grouping` field (defaults to None)
- Existing saved states without `color_grouping` should still work
- Migration: old states will have `color_grouping=None`, which is valid

**Code location:**
- `plot_state.py` ~line 74 (`from_dict` method)

---

## Phase 7: Testing Considerations

### 7.1 Test Cases

**Box Plot:**
1. `group_col` = categorical, `color_grouping` = None → single trace per x category
2. `group_col` = categorical, `color_grouping` = categorical → nested grouping (x-axis by group_col, color by color_grouping)
3. `group_col` = "(none)" → show validation error

**Violin Plot:**
- Same test cases as box plot

**Swarm Plot:**
- Same as box/violin, plus verify jitter works correctly with nested grouping
- Verify points don't overlap incorrectly when both `group_col` and `color_grouping` are set

**Histogram (if implemented):**
- `xcol` = numeric, `group_col` = categorical, `color_grouping` = categorical → grouped histograms
- Verify bins are calculated correctly with grouping

### 7.2 Edge Cases

- Empty data after filtering
- Missing values in `group_col` or `color_grouping`
- Single category in `group_col` or `color_grouping`
- Very large number of categories (performance)

---

## Implementation Order

1. **Phase 1:** Data model (PlotState) - Foundation
2. **Phase 2:** UI (add color_grouping select) - User interface
3. **Phase 3:** Box/Violin/Swarm plot generation - Core functionality
4. **Phase 4:** Histogram (optional, can defer) - Extended functionality
5. **Phase 5:** Scatter (keep current behavior) - No changes needed
6. **Phase 6:** Validation - Safety and UX
7. **Phase 7:** Testing - Quality assurance

---

## Questions to Clarify

1. **Scatter plots:** Keep using `xcol` for x-axis, or switch to `group_col`?
   - **Recommendation:** Keep `xcol` (supports numeric x)

2. **Histogram:** Implement now or defer?
   - **Recommendation:** Defer to Phase 4, focus on box/violin/swarm first

3. **X column aggrid:** For box/violin/swarm, should it be hidden/disabled when these plot types are selected?
   - **Recommendation:** Keep visible but show hint that it's not used for these plot types

4. **Group/Color label:** Rename to "Group (X-axis)" or keep as "Group/Color"?
   - **Recommendation:** Keep "Group/Color" for now, add tooltip/hint explaining it's used for x-axis in box/violin/swarm

5. **Color Grouping label:** "Group/Nesting" vs "Color Grouping" vs "Nested Group"?
   - **Recommendation:** "Group/Nesting" or "Color Grouping" - both are clear

---

## Summary

This plan implements Option B by:
- Adding `color_grouping` field for nested grouping
- Restructuring `group_col` to serve as x-axis for box/violin/swarm plots
- Using Plotly's native `color` parameter for nested grouping
- Maintaining backward compatibility
- Focusing on box/violin/swarm first, with histogram/scatter as follow-ups

The key insight is that Plotly's `go.Box()` and `go.Violin()` support a `color` parameter that automatically creates nested grouping when combined with `x` parameter. This is more efficient than manually creating multiple traces.

---

## Notes

- Plotly's `color` parameter in `go.Box()`/`go.Violin()` automatically handles nested grouping
- This is more efficient than the current manual trace-per-group approach
- The restructure makes the grouping semantics clearer: `group_col` = x-axis grouping, `color_grouping` = nested color grouping
- Backward compatibility is maintained through `from_dict()` defaulting `color_grouping` to None
