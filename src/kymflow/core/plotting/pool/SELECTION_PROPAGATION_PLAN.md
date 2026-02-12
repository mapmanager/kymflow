# User Selection with Rect/Lasso and Propagation - Implementation Plan

## Overview
Implement user selection (rect/lasso) in Plotly plots and propagate selections across compatible plots.

## Phase 1: Implement Selection Callbacks

### 1.1 Add Plotly Event Handlers
- **Location**: `demo_pool_app.py` - `_rebuild_plot_panel()` method
- **Action**: Register `plotly_selected` event handler **only for compatible plot types**
- **Compatible plot types**: `SCATTER`, `SPLIT_SCATTER`, `SWARM`
- **Incompatible plot types**: `GROUPED`, `CUMULATIVE_HISTOGRAM` - **NO callback registered**
- **Logic**: Check `plot_state.plot_type` before registering callback
- **Event Data Structure**:
  ```python
  {
    "points": [
      {
        "customdata": row_id,  # or [row_id, ...] for swarm plots
        "x": x_value,
        "y": y_value,
        "pointIndex": int,
        "curveNumber": int,
        ...
      },
      ...
    ]
  }
  ```

### 1.2 Create Selection Callback Method
- **Method**: `_on_plotly_selected(self, e: GenericEventArguments, plot_index: int)`
- **Responsibilities**:
  - Extract selected points from event
  - Extract row_ids from `customdata` of each point
  - Handle different customdata formats:
    - String/int/float: single row_id
    - List/tuple: first element is row_id (for swarm plots)
  - Convert row_ids to a set for deduplication
  - Log selection details
  - Call Phase 2 handler to store selection

### 1.3 Handle Edge Cases
- Empty selection (user deselects)
- Invalid/missing customdata
- Multiple traces (split_scatter with groups)
- Swarm plots with 2D customdata arrays

### 1.4 Testing
- Test rect selection (box select)
- Test lasso selection
- Test deselection (double-click or clear)
- Verify row_ids are correctly extracted

---

## Phase 2: Data Structure for User Selection

### 2.1 Create SelectionState Class
- **File**: `kymflow/src/kymflow/core/plotting/pool/selection_state.py` (NEW)
- **Structure**:
  ```python
  @dataclass
  class SelectionState:
      """Represents user selection of data points across plots.
      
      Attributes:
          selected_row_ids: Set of row_id strings that are currently selected.
          source_plot_index: Index of plot where selection originated (0-based).
          timestamp: When selection was made (for debugging/logging).
      """
      selected_row_ids: set[str]
      source_plot_index: int
      timestamp: float  # time.time()
      
      def to_dict(self) -> dict[str, Any]:
          """Serialize to dict for debugging/logging."""
          ...
      
      @classmethod
      def empty(cls, source_plot_index: int = 0) -> "SelectionState":
          """Create empty selection."""
          ...
  ```

### 2.2 Add SelectionState to PlotController
- **Location**: `PlotController.__init__()`
- **Action**: Add `self.selection_state: Optional[SelectionState] = None`
- **Purpose**: Store current selection state

### 2.3 Update Selection State
- **Method**: `_update_selection_state(self, row_ids: set[str], source_plot_index: int)`
- **Responsibilities**:
  - Create new `SelectionState` from row_ids
  - Store in `self.selection_state`
  - Log selection update
  - Trigger Phase 3 propagation

### 2.4 Selection Compatibility Check
- **Method**: `_is_selection_compatible(plot_type: PlotType) -> bool`
- **Logic**:
  ```python
  SELECTION_COMPATIBLE_TYPES = {
      PlotType.SCATTER,
      PlotType.SPLIT_SCATTER,
      PlotType.SWARM,
  }
  SELECTION_INCOMPATIBLE_TYPES = {
      PlotType.GROUPED,
      PlotType.CUMULATIVE_HISTOGRAM,
  }
  ```
- **Purpose**: Formally encode which plot types support selection propagation

---

## Phase 3: Propagate Selection to Other Plots

### 3.1 Visual Selection Indicators
- **Approach**: Update plot traces to highlight selected points
- **Methods**:
  - `_apply_selection_to_plot(plot_index: int, selection_state: SelectionState) -> None`
  - `_clear_selection_from_plot(plot_index: int) -> None`

### 3.2 Selection Visualization Strategy
- **Option A**: Update marker colors/sizes for selected points
  - Selected: different color (e.g., red) or larger size
  - Unselected: default color/size
- **Option B**: Add selection overlay shapes (rectangles around selected points)
- **Option C**: Update trace opacity (selected=1.0, unselected=0.3)
- **Recommendation**: Start with Option A (marker color), simplest and most visible

### 3.3 Propagation Logic
- **Method**: `_propagate_selection(self, source_plot_index: int, selection_state: SelectionState) -> None`
- **Algorithm**:
  1. Iterate through all plots (0 to len(self._plots) - 1)
  2. Skip source plot (already has selection)
  3. Check if plot type is selection-compatible using `_is_selection_compatible()`
  4. **If compatible** (SCATTER, SPLIT_SCATTER, SWARM):
     - Get current plot state
     - Filter dataframe by ROI
     - Map row_ids to plot's filtered dataframe indices
     - Update plot figure with selection highlighting
  4. **If incompatible** (GROUPED, CUMULATIVE_HISTOGRAM):
     - **Skip silently** - no callback registered, no propagation attempted
     - No logging needed (expected behavior)

### 3.4 Row ID Mapping
- **Challenge**: Different plots may have different ROI filters
- **Solution**: 
  - Each plot has its own filtered dataframe (`filter_by_roi(state.roi_id)`)
  - Selection row_ids are global (from full dataframe)
  - Need to map: `global_row_id -> filtered_df_index` for each plot
- **Method**: `_map_row_ids_to_plot_indices(self, plot_index: int, row_ids: set[str]) -> set[int]`
  - Filter dataframe by plot's ROI
  - Build row_id -> filtered_index mapping
  - Return set of filtered indices that match selected row_ids

### 3.5 Update Plot Figure with Selection
- **Location**: `figure_generator.py` or new method in `PlotController`
- **Method**: `_apply_selection_to_figure_dict(figure_dict: dict, selected_indices: set[int], trace_index: int = 0) -> dict`
- **Logic**:
  - Get trace data (x, y arrays)
  - Create new trace with selected points (different color)
  - Create new trace with unselected points (default color, lower opacity)
  - Or: Update existing trace with marker colors array
- **Plotly Approach**:
  ```python
  # Option: Update marker colors
  colors = ['red' if i in selected_indices else 'blue' for i in range(len(x))]
  trace['marker']['color'] = colors
  ```

### 3.6 Handle Multiple Traces (Split Scatter)
- **Challenge**: Split scatter has multiple traces (one per group)
- **Solution**:
  - Iterate through all traces in figure
  - For each trace, check which points (by customdata) are selected
  - Apply selection highlighting per trace

### 3.7 Replot with Selection
- **Method**: `_replot_with_selection(self, plot_index: int) -> None`
- **Flow**:
  1. Get current plot state
  2. Generate figure dict (via `_make_figure_dict()`)
  3. Apply selection highlighting (via `_apply_selection_to_figure_dict()`)
  4. Update plot widget (via `plot.update_figure()`)

### 3.8 Clear Selection
- **Method**: `_clear_all_selections(self) -> None`
- **Action**:
  - Set `self.selection_state = None`
  - Replot all compatible plots without selection highlighting

### 3.9 UI Feedback
- **Optional**: Add a label showing selection count
- **Location**: Control panel
- **Format**: "Selected: N points" or "No selection"

---

## Implementation Order

1. **Phase 1** (Selection Callbacks)
   - Add `plotly_selected` event handlers
   - Implement `_on_plotly_selected()` method
   - Test with rect and lasso selection

2. **Phase 2** (Data Structure)
   - Create `selection_state.py` with `SelectionState` class
   - Add selection state to `PlotController`
   - Implement `_update_selection_state()` and `_is_selection_compatible()`

3. **Phase 3** (Propagation)
   - Implement `_map_row_ids_to_plot_indices()`
   - Implement `_apply_selection_to_figure_dict()`
   - Implement `_propagate_selection()`
   - Test propagation between plot 1 and plot 2

---

## Technical Considerations

### Row ID Consistency
- Ensure `row_id_col` values are consistent across plots
- Handle cases where row_id might not exist in filtered dataframe (different ROI)

### Performance
- Selection updates should be fast (<100ms)
- Consider debouncing if user drags selection box rapidly
- Cache filtered dataframe indices if needed

### Edge Cases
- Plot 1 and Plot 2 have different ROIs (some row_ids won't exist in both)
- Plot 1 is scatter, Plot 2 is grouped (propagation skipped)
- User switches plot type after making selection (clear selection?)
- User changes layout (1x1 to 1x2) with active selection (preserve selection)

### Testing Strategy
1. Single plot selection (no propagation)
2. Two compatible plots (scatter -> scatter)
3. Two incompatible plots (scatter -> grouped, should skip)
4. Mixed compatibility (scatter -> split_scatter -> swarm)
5. Different ROIs (selection should only propagate to matching row_ids)
6. Clear selection (double-click or button)

---

## Files to Create/Modify

### New Files
- `kymflow/src/kymflow/core/plotting/pool/selection_state.py` - SelectionState dataclass

### Modified Files
- `demo_pool_app.py`:
  - Add `plotly_selected` event handlers in `_rebuild_plot_panel()`
  - Add `_on_plotly_selected()` method
  - Add `_update_selection_state()` method
  - Add `_is_selection_compatible()` method
  - Add `_propagate_selection()` method
  - Add `_map_row_ids_to_plot_indices()` method
  - Add `_apply_selection_to_figure_dict()` method
  - Add `_replot_with_selection()` method
  - Add `_clear_all_selections()` method
  - Add `selection_state` attribute to `PlotController`

### Optional Modifications
- `figure_generator.py`: Add selection highlighting support (if we want to keep figure generation pure)
- Or: Keep selection highlighting in `PlotController` (simpler, but mixes concerns)

---

## Success Criteria

- [ ] User can select points with rect tool in any compatible plot
- [ ] User can select points with lasso tool in any compatible plot
- [ ] Selection is visually highlighted (different color/size)
- [ ] Selection in plot 1 propagates to plot 2 (if compatible)
- [ ] Selection in plot 2 propagates to plot 1 (if compatible)
- [ ] Selection does NOT propagate to incompatible plot types
- [ ] Selection persists when switching between plots
- [ ] Selection can be cleared (double-click or button)
- [ ] Selection works correctly with different ROIs
- [ ] Selection works correctly with multiple traces (split_scatter)
