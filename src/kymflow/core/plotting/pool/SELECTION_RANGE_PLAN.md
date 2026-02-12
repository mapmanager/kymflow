# Selection Range/BBox Approach - Implementation Plan

## Problem
`plotly_selected` events transmit all selected point data (x, y, fullData, etc.), causing payload size to exceed NiceGUI limits (e.g., 3MB+).

## Solution
Instead of transmitting all selected points, transmit only the **selection geometry** (range/bbox for box select, polygon for lasso), then compute which points are selected on the server side.

---

## Phase 1: Modify `_on_plotly_selected` to Extract Selection Geometry

### 1.1 Understand Plotly Event Structure
- **Box Select**: Event args may contain:
  - `range`: `{x: [x0, x1], y: [y0, y1]}` - selection bounding box
  - OR `selections`: array with `{x0, x1, y0, y1, type: 'rect'}` 
  - OR `points`: array of selected points (current approach - TOO LARGE)
  
- **Lasso Select**: Event args may contain:
  - `lassoPoints`: polygon coordinates `{x: [...], y: [...]}`
  - OR `points`: array of selected points (current approach - TOO LARGE)

### 1.2 Update `_on_plotly_selected` Method
**Location**: `demo_pool_app.py` - `_on_plotly_selected()`

**Changes**:
1. **Check for range/bbox first** (box select):
   ```python
   event_args = e.args or {}
   
   # Try to get selection range/bbox (preferred - small payload)
   selection_range = event_args.get("range")
   if selection_range:
       x_range = selection_range.get("x", [])
       y_range = selection_range.get("y", [])
       # Use range to compute selected points
   ```

2. **Check for selections array** (alternative format):
   ```python
   selections = event_args.get("selections", [])
   if selections and len(selections) > 0:
       sel = selections[0]  # Use first selection
       if sel.get("type") == "rect":
           x0, x1 = sel.get("x0"), sel.get("x1")
           y0, y1 = sel.get("y0"), sel.get("y1")
           # Use bbox to compute selected points
   ```

3. **Check for lassoPoints** (lasso select):
   ```python
   lasso_points = event_args.get("lassoPoints")
   if lasso_points:
       lasso_x = lasso_points.get("x", [])
       lasso_y = lasso_points.get("y", [])
       # Use polygon to compute selected points
   ```

4. **Fallback to points array** (only if geometry not available):
   ```python
   # Only use points array if range/bbox/lassoPoints not available
   points = event_args.get("points", [])
   if points and not (selection_range or selections or lasso_points):
       # Extract customdata only (minimal processing)
   ```

### 1.3 Log Event Structure for Debugging
Add detailed logging to understand what fields are actually available:
```python
logger.debug(f"plotly_selected event args keys: {list(event_args.keys())}")
if "range" in event_args:
    logger.debug(f"Found range: {event_args['range']}")
if "selections" in event_args:
    logger.debug(f"Found selections: {event_args['selections']}")
if "lassoPoints" in event_args:
    logger.debug(f"Found lassoPoints: {event_args['lassoPoints']}")
```

---

## Phase 2: Implement Server-Side Point Selection Computation

### 2.1 Create Helper Method: `_compute_selected_points_from_range`
**Location**: `demo_pool_app.py`

**Purpose**: Given a selection range/bbox, compute which points in the filtered dataframe are selected.

**Signature**:
```python
def _compute_selected_points_from_range(
    self,
    df_f: pd.DataFrame,
    state: PlotState,
    x_range: Optional[tuple[float, float]] = None,
    y_range: Optional[tuple[float, float]] = None,
) -> set[str]:
    """Compute selected row_ids from selection range/bbox.
    
    Args:
        df_f: Filtered dataframe (already filtered by ROI).
        state: PlotState with xcol, ycol, plot_type.
        x_range: (x_min, x_max) for box select, or None.
        y_range: (y_min, y_max) for box select, or None.
        
    Returns:
        Set of row_id strings that fall within the selection range.
    """
```

**Implementation**:
1. Get x and y values from dataframe:
   ```python
   x = df_f[state.xcol]
   y = self.data_processor.get_y_values(df_f, state.ycol, state.use_absolute_value)
   row_ids = df_f[self.row_id_col].astype(str)
   ```

2. For **box select** (x_range and y_range provided):
   ```python
   if x_range and y_range:
       x_min, x_max = x_range
       y_min, y_max = y_range
       mask = (x >= x_min) & (x <= x_max) & (y >= y_min) & (y <= y_max)
       selected_row_ids = set(row_ids[mask].tolist())
   ```

3. For **lasso select** (polygon):
   - Use point-in-polygon algorithm (e.g., `shapely` or `matplotlib.path.Path.contains_points`)
   - Filter points that fall inside the polygon

4. Handle **categorical x columns** (see "Categorical axes" section below).

### 2.2 Create Helper Method: `_compute_selected_points_from_lasso`
**Location**: `demo_pool_app.py`

**Purpose**: Given lasso polygon coordinates, compute which points are selected.

**Signature**:
```python
def _compute_selected_points_from_lasso(
    self,
    df_f: pd.DataFrame,
    state: PlotState,
    lasso_x: list[float],
    lasso_y: list[float],
) -> set[str]:
    """Compute selected row_ids from lasso polygon.
    
    Args:
        df_f: Filtered dataframe (already filtered by ROI).
        state: PlotState with xcol, ycol, plot_type.
        lasso_x: List of x coordinates forming polygon.
        lasso_y: List of y coordinates forming polygon.
        
    Returns:
        Set of row_id strings that fall inside the polygon.
    """
```

**Implementation**:
- Use `matplotlib.path.Path` for point-in-polygon test:
  ```python
  from matplotlib.path import Path
  
  polygon = Path(list(zip(lasso_x, lasso_y)))
  x = df_f[state.xcol]
  y = self.data_processor.get_y_values(df_f, state.ycol, state.use_absolute_value)
  points = np.column_stack([x, y])
  mask = polygon.contains_points(points)
  row_ids = df_f[self.row_id_col].astype(str)
  selected_row_ids = set(row_ids[mask].tolist())
  ```

### 2.3 Handle Special Cases
- **Empty selection**: Return empty set
- **Categorical axes**: See section below.

---

## Categorical axes (x or y as non-numeric, e.g. string)

When an axis is **categorical** (e.g. string column like `grandparent_folder` on x), Plotly still sends `range` in **axis space**, which is **category index space**: categories are at positions 0, 1, 2, … (and possibly fractional, e.g. 0.5–2.3 for a box).

### How to interpret `range.x` or `range.y` for categorical axes

- **Numeric axis**: `[min, max]` is in data units; include points where `min <= value <= max`.
- **Categorical axis**: `[min, max]` is in **index space** (0 = first category, 1 = second, etc.).  
  - Compute ordered list of categories (e.g. `sorted(df[col].dropna().unique())` to match Plotly’s usual ordering).
  - Map range to category indices: e.g. indices `i` where `min <= i <= max` (or use floor/ceil: `range(int(min), int(max)+1)`).
  - Include rows whose value is in `categories[i]` for those indices.

### Per plot type

- **Scatter / Split scatter**: x (or y) can be numeric or categorical. If categorical, use the same ordered categories as in the figure; convert range to set of categories, then `mask = df[col].isin(categories_in_range)`.
- **Swarm**: x is always categorical in the data, but the figure uses **numeric positions** (category index + jitter). So the event range is already in that numeric space. We must recompute the same x positions (category index + deterministic jitter) and compare `(x_pos, y)` to the range. Reuse the same jitter logic as in `_figure_swarm` (e.g. in `FigureGenerator.get_axis_x_for_selection()`).

### Implementation approach

- Add `FigureGenerator.get_axis_x_for_selection(df_f, state)` that returns a `pd.Series` of x values in **plot axis space** (numeric):
  - Scatter/split_scatter, numeric x: `df_f[xcol]` as float.
  - Scatter/split_scatter, categorical x: map categories to 0, 1, 2, … (same order as in figure).
  - Swarm: category index + deterministic jitter (same as `_figure_swarm`).
- `_compute_selected_points_from_range` then uses this series and compares to `x_range`/`y_range` in the same units. Y is always numeric from `get_y_values`.

---

## Phase 3: Update `_on_plotly_selected` to Use Range-Based Computation

### 3.1 Refactor Method Flow
```python
def _on_plotly_selected(self, e: GenericEventArguments, plot_index: int = 0) -> None:
    """Handle selection events using range/bbox instead of points array."""
    event_args = e.args or {}
    state = self.plot_states[plot_index]
    
    # Get filtered dataframe
    df_f = self.data_processor.filter_by_roi(state.roi_id)
    
    selected_row_ids: set[str] = set()
    
    # Priority 1: Try range/bbox (box select)
    selection_range = event_args.get("range")
    if selection_range:
        x_range = selection_range.get("x", [])
        y_range = selection_range.get("y", [])
        if len(x_range) == 2 and len(y_range) == 2:
            selected_row_ids = self._compute_selected_points_from_range(
                df_f, state,
                x_range=(x_range[0], x_range[1]),
                y_range=(y_range[0], y_range[1])
            )
    
    # Priority 2: Try selections array (alternative format)
    elif event_args.get("selections"):
        selections = event_args.get("selections", [])
        if selections and selections[0].get("type") == "rect":
            sel = selections[0]
            selected_row_ids = self._compute_selected_points_from_range(
                df_f, state,
                x_range=(sel.get("x0"), sel.get("x1")),
                y_range=(sel.get("y0"), sel.get("y1"))
            )
    
    # Priority 3: Try lassoPoints (lasso select)
    elif event_args.get("lassoPoints"):
        lasso_points = event_args.get("lassoPoints")
        selected_row_ids = self._compute_selected_points_from_lasso(
            df_f, state,
            lasso_x=lasso_points.get("x", []),
            lasso_y=lasso_points.get("y", [])
        )
    
    # Priority 4: Fallback to points array (only if geometry not available)
    else:
        points = event_args.get("points", [])
        if points:
            # Extract only customdata (minimal payload)
            for point in points:
                custom = point.get("customdata")
                # ... existing extraction logic ...
    
    # Handle empty selection
    if not selected_row_ids:
        logger.info(f"Selection cleared on plot {plot_index + 1}")
        # TODO: Phase 2 - Clear selection state
        return
    
    logger.info(
        f"Selection on plot {plot_index + 1}: "
        f"plot_type={state.plot_type.value}, "
        f"selected_count={len(selected_row_ids)}, "
        f"roi_id={state.roi_id}"
    )
    
    # TODO: Phase 2 - Store selection state and propagate
```

---

## Phase 4: Testing and Edge Cases

### 4.1 Test Cases
1. **Box select** (rect tool):
   - Small selection (few points)
   - Large selection (many points)
   - Selection spanning multiple traces (split_scatter)
   - Selection on categorical x-axis (swarm plot)

2. **Lasso select**:
   - Simple polygon
   - Complex polygon with many vertices
   - Polygon spanning multiple traces

3. **Edge cases**:
   - Empty selection (deselect)
   - Selection outside data range
   - Selection on plot with no data
   - Categorical x columns

### 4.2 Debugging
- Add logging to show which selection method was used (range/bbox/lasso/points)
- Log selection geometry (x_range, y_range, or lasso point count)
- Verify computed selected_row_ids match expected points

---

## Implementation Order

1. **Step 1**: Add logging to `_on_plotly_selected` to inspect event structure
2. **Step 2**: Implement `_compute_selected_points_from_range` for box select
3. **Step 3**: Update `_on_plotly_selected` to use range/bbox when available
4. **Step 4**: Test box select with range/bbox approach
5. **Step 5**: Implement `_compute_selected_points_from_lasso` for lasso select
6. **Step 6**: Update `_on_plotly_selected` to handle lasso
7. **Step 7**: Test lasso select
8. **Step 8**: Remove/update fallback to points array (or keep as last resort)

---

## Notes

- **Example data**: e.g. `radon_report.csv` can have categorical axes (e.g. string column on x); selection range must be interpreted in category index space as above.
- **Payload size**: Range/bbox is ~100 bytes vs. points array which can be 3MB+
- **Accuracy**: Range-based computation should match client-side selection exactly
- **Performance**: Server-side computation is fast (pandas boolean indexing)
- **Compatibility**: May need to handle different event formats from different Plotly versions
