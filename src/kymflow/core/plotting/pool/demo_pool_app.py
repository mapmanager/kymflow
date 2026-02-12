# app.py
from __future__ import annotations

from typing import Any, Optional

from pprint import pprint
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from nicegui import ui
from nicegui.events import GenericEventArguments

from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.gui_v2.app_context import _setUpGuiDefaults
from kymflow.core.plotting.pool.plot_state import PlotType, PlotState
from kymflow.core.plotting.pool.plot_helpers import (
    numeric_columns,
    categorical_candidates,
    _ensure_aggrid_compact_css,
)
from kymflow.core.plotting.pool.dataframe_processor import DataFrameProcessor

logger = get_logger(__name__)
setup_logging(level="INFO")


# ----------------------------
# Controller
# ----------------------------

class PlotController:
    def __init__(
        self,
        df: pd.DataFrame,
        *,
        roi_id_col: str = "roi_id",
        row_id_col: str = "path",
    ) -> None:
        """Initialize plot controller with dataframe and column configuration.
        
        Args:
            df: DataFrame containing plot data with required columns.
            roi_id_col: Column name containing ROI identifiers.
            row_id_col: Column name containing unique row identifiers.
        """
        self.df = df
        self.roi_id_col = roi_id_col
        self.row_id_col = row_id_col

        # Initialize DataFrameProcessor for data operations
        self.data_processor = DataFrameProcessor(
            df,
            roi_id_col=roi_id_col,
            row_id_col=row_id_col,
        )

        # reasonable defaults
        num_cols = numeric_columns(df)
        if not num_cols:
            raise ValueError("Need at least one numeric column for y.")
        x_default = num_cols[0]
        y_default = num_cols[1] if len(num_cols) >= 2 else num_cols[0]
        
        roi_values = self.data_processor.get_roi_values()

        # Initialize with 2 plot states (extensible to 4)
        default_state = PlotState(
            roi_id=roi_values[0],
            xcol=x_default,
            ycol=y_default,
        )
        self.plot_states: list[PlotState] = [
            PlotState.from_dict(default_state.to_dict()),
            PlotState.from_dict(default_state.to_dict()),
        ]
        self.current_plot_index: int = 0
        self.layout: str = "1x1"

        # UI handles
        self._plots: list[ui.plotly] = []
        self._clicked_label: Optional[ui.label] = None
        self._mainSplitter: Optional[ui.splitter] = None
        self._plot_container: Optional[ui.column] = None  # Container inside splitter slot for clearing

        self._roi_select: Optional[ui.select] = None
        self._type_select: Optional[ui.select] = None
        self._x_aggrid: Optional[ui.aggrid] = None
        self._y_aggrid: Optional[ui.aggrid] = None
        self._group_select: Optional[ui.select] = None
        self._ystat_select: Optional[ui.select] = None
        self._abs_value_checkbox: Optional[ui.checkbox] = None

        # row_id -> iloc index within CURRENT filtered df (rebuilt each replot)
        self._id_to_index_filtered: dict[str, int] = {}

    # ----------------------------
    # Data
    # ----------------------------
    # Note: DataFrame operations are now handled by self.data_processor
    
    def _state_to_widgets(self, state: PlotState) -> None:
        """Populate all UI widgets from a PlotState.
        
        Args:
            state: PlotState to load into UI widgets.
        """
        assert (
            self._roi_select and self._type_select and self._group_select 
            and self._ystat_select and self._abs_value_checkbox
            and self._show_mean_checkbox and self._show_std_sem_checkbox and self._std_sem_select
            and self._mean_line_width_input and self._error_line_width_input and self._show_raw_checkbox
            and self._point_size_input and self._show_legend_checkbox
            and self._x_aggrid and self._y_aggrid
        )
        
        # Basic controls
        self._roi_select.value = state.roi_id
        self._type_select.value = state.plot_type.value
        self._ystat_select.value = state.ystat
        self._group_select.value = state.group_col if state.group_col else "(none)"
        self._abs_value_checkbox.value = state.use_absolute_value
        
        # Mean/Std/Sem controls
        self._show_mean_checkbox.value = state.show_mean
        self._show_std_sem_checkbox.value = state.show_std_sem
        self._std_sem_select.value = state.std_sem_type
        
        # Plot options
        self._mean_line_width_input.value = state.mean_line_width
        self._error_line_width_input.value = state.error_line_width
        self._show_raw_checkbox.value = state.show_raw
        self._point_size_input.value = state.point_size
        self._show_legend_checkbox.value = state.show_legend
        
        # AgGrid selections (use run_row_method to select)
        try:
            self._x_aggrid.run_row_method(state.xcol, "setSelected", True, True)
        except Exception:
            pass  # Grid may not be ready
        try:
            self._y_aggrid.run_row_method(state.ycol, "setSelected", True, True)
        except Exception:
            pass  # Grid may not be ready
        
        # Sync control enable/disable state
        self._sync_controls()
    
    def _widgets_to_state(self) -> PlotState:
        """Create PlotState from current UI widget values.
        
        Returns:
            PlotState created from current widget values.
        """
        assert (
            self._roi_select and self._type_select and self._group_select 
            and self._ystat_select and self._abs_value_checkbox
            and self._show_mean_checkbox and self._show_std_sem_checkbox and self._std_sem_select
            and self._mean_line_width_input and self._error_line_width_input and self._show_raw_checkbox
            and self._point_size_input and self._show_legend_checkbox
        )
        
        roi_id = int(self._roi_select.value)
        plot_type_str = str(self._type_select.value)
        try:
            plot_type = PlotType(plot_type_str)
        except ValueError:
            logger.warning(f"Invalid plot type '{plot_type_str}', defaulting to SCATTER")
            plot_type = PlotType.SCATTER
        
        gv = str(self._group_select.value)
        group_col = None if gv == "(none)" else gv
        
        # Get xcol/ycol from current state (they're updated via aggrid callbacks)
        current_state = self.plot_states[self.current_plot_index]
        return PlotState(
            roi_id=roi_id,
            xcol=current_state.xcol,  # Preserve xcol (updated via aggrid callback)
            ycol=current_state.ycol,  # Preserve ycol (updated via aggrid callback)
            plot_type=plot_type,
            group_col=group_col,
            ystat=str(self._ystat_select.value),
            use_absolute_value=bool(self._abs_value_checkbox.value),
            show_mean=bool(self._show_mean_checkbox.value),
            show_std_sem=bool(self._show_std_sem_checkbox.value),
            std_sem_type=str(self._std_sem_select.value),
            mean_line_width=int(self._mean_line_width_input.value) if self._mean_line_width_input.value is not None else 2,
            error_line_width=int(self._error_line_width_input.value) if self._error_line_width_input.value is not None else 2,
            show_raw=bool(self._show_raw_checkbox.value),
            point_size=int(self._point_size_input.value) if self._point_size_input.value is not None else 6,
            show_legend=bool(self._show_legend_checkbox.value),
        )


    def _add_mean_std_traces(
        self, 
        fig: go.Figure, 
        group_stats: dict[str, dict[str, float]], 
        x_ranges: dict[str, tuple[float, float]],
        state: PlotState,
        include_x_axis: bool = False,
    ) -> None:
        """Add mean and std/sem traces to figure.
        
        Args:
            fig: Plotly figure to add traces to.
            group_stats: Dictionary from DataFrameProcessor.calculate_group_stats().
            x_ranges: Dictionary mapping group_value to (x_min, x_max) tuple.
            state: PlotState to use for configuration.
            include_x_axis: If True, also add x-axis mean/std/sem (for split_scatter).
        """
        if not group_stats or not x_ranges:
            return
        
        for group_value, stats in group_stats.items():
            if group_value not in x_ranges:
                continue
            
            x_min, x_max = x_ranges[group_value]
            mean_val = stats["mean"]
            
            # Add horizontal line for y-mean (hide from legend - only show primary traces)
            if state.show_mean:
                fig.add_trace(go.Scatter(
                    x=[x_min, x_max],
                    y=[mean_val, mean_val],
                    mode="lines",
                    name=f"{group_value} (y-mean)",
                    line=dict(color="gray", width=state.mean_line_width),
                    showlegend=False,  # Hide mean/std/sem traces from legend
                    hovertemplate=f"Y Mean: {mean_val:.3f}<extra></extra>",
                ))
            
            # Add vertical line for y-std/sem (hide from legend)
            if state.show_std_sem:
                error_val = stats[state.std_sem_type]
                y_min = mean_val - error_val
                y_max = mean_val + error_val
                x_center = (x_min + x_max) / 2
                
                fig.add_trace(go.Scatter(
                    x=[x_center, x_center],
                    y=[y_min, y_max],
                    mode="lines",
                    name=f"{group_value} (y-{state.std_sem_type})",
                    line=dict(color="red", width=state.error_line_width),
                    showlegend=False,  # Hide mean/std/sem traces from legend
                    hovertemplate=(
                        f"Y Mean: {mean_val:.3f}<br>"
                        f"Y {state.std_sem_type.upper()}: ±{error_val:.3f}<br>"
                        f"Y Range: [{y_min:.3f}, {y_max:.3f}]<extra></extra>"
                    ),
                ))
            
            # Add x-axis mean and std/sem for split_scatter (hide from legend)
            if include_x_axis and "x_mean" in stats:
                x_mean_val = stats["x_mean"]
                x_error_val = stats[f"x_{state.std_sem_type}"]
                
                # Calculate y range for x-mean vertical line
                # Use y-std/sem range if available, otherwise use a range around y-mean
                if state.show_std_sem:
                    y_line_min = y_min
                    y_line_max = y_max
                else:
                    # Use a reasonable range around y-mean (10% of mean or fixed range)
                    y_range = abs(mean_val) * 0.1 if mean_val != 0 else 1.0
                    y_line_min = mean_val - y_range
                    y_line_max = mean_val + y_range
                
                # Add vertical line for x-mean
                if state.show_mean:
                    fig.add_trace(go.Scatter(
                        x=[x_mean_val, x_mean_val],
                        y=[y_line_min, y_line_max],
                        mode="lines",
                        name=f"{group_value} (x-mean)",
                        line=dict(color="blue", width=state.mean_line_width),
                        showlegend=False,  # Hide mean/std/sem traces from legend
                        hovertemplate=f"X Mean: {x_mean_val:.3f}<extra></extra>",
                    ))
                
                # Add horizontal line for x-std/sem
                if state.show_std_sem:
                    x_min_error = x_mean_val - x_error_val
                    x_max_error = x_mean_val + x_error_val
                    y_center = mean_val
                    
                    fig.add_trace(go.Scatter(
                        x=[x_min_error, x_max_error],
                        y=[y_center, y_center],
                        mode="lines",
                        name=f"{group_value} (x-{state.std_sem_type})",
                        line=dict(color="orange", width=state.error_line_width),
                        showlegend=False,  # Hide mean/std/sem traces from legend
                        hovertemplate=(
                            f"X Mean: {x_mean_val:.3f}<br>"
                            f"X {state.std_sem_type.upper()}: ±{x_error_val:.3f}<br>"
                            f"X Range: [{x_min_error:.3f}, {x_max_error:.3f}]<extra></extra>"
                        ),
                    ))

    # ----------------------------
    # UI
    # ----------------------------

    def build(self) -> None:
        """Build the main UI layout with header, splitter, controls, and plot."""
        # Header area at the top
        with ui.column().classes("w-full"):
            ui.label("Radon Analysis Pool Plot").classes("text-2xl font-bold mb-2")
            self._clicked_label = ui.label("Click a point to show the filtered df row...").classes("text-sm text-gray-600")
        
        # Main splitter: horizontal layout with controls on left, plot on right
        self._mainSplitter = ui.splitter(value=25, limits=(15, 50)).classes("w-full h-screen")
        
        # LEFT: Control panel (modular, can be reused elsewhere)
        with self._mainSplitter.before:
            self._build_control_panel()
        
        # RIGHT: Plot panel (modular, can be reused elsewhere)
        # Create a container inside the splitter slot that we can clear
        with self._mainSplitter.after:
            self._plot_container = ui.column().classes("w-full h-full")
        # Build the plot panel inside the container
        self._rebuild_plot_panel()

        self._sync_controls()
        # Initial state is already loaded into widgets, just sync
        self._state_to_widgets(self.plot_states[self.current_plot_index])

    def _build_control_panel(self) -> None:
        """Build the left control panel with all plot configuration widgets.
        
        Creates a modular control panel that can be inserted into any container.
        All widgets are stored as instance attributes for later access.
        """
        with ui.column().classes("w-full h-full p-4 gap-4 overflow-y-auto"):
            # Layout selection
            self._layout_select = ui.select(
                options={"1x1": "1x1", "1x2": "1x2", "2x1": "2x1"},
                value=self.layout,
                label="Layout",
                on_change=lambda e: self._on_layout_change(str(e.value)),
            ).classes("w-full")
            
            # Plot selection (radio buttons) - label and radios in same row
            with ui.row().classes("w-full gap-2 items-center"):
                ui.label("Edit Plot").classes("text-sm font-semibold")
                self._plot_radio = ui.radio(
                    ["1", "2"],
                    value="1",
                    on_change=lambda e: self._on_plot_selection_change(int(e.value) - 1),
                ).props("inline")
            
            # Apply to other button
            self._apply_to_other_button = ui.button(
                "Apply to Other",
                on_click=self._apply_current_to_others,
            ).classes("w-full")
            
            self._roi_select = ui.select(
                options=self.data_processor.get_roi_values(),
                value=self.plot_states[self.current_plot_index].roi_id,
                label="ROI",
                on_change=self._on_any_change,
            ).classes("w-full")

            self._type_select = ui.select(
                options={pt.value: pt.value for pt in PlotType},
                value=self.plot_states[self.current_plot_index].plot_type.value,
                label="Plot type",
                on_change=self._on_any_change,
            ).classes("w-full")

            group_options = ["(none)"] + categorical_candidates(self.df)
            logger.info(f"group_options: {group_options}")
            self._group_select = ui.select(
                options=group_options,
                value="(none)",
                label="Group/Color",
                on_change=self._on_any_change,
            ).classes("w-full")

            self._ystat_select = ui.select(
                options=["mean", "median", "sum", "count", "std", "min", "max"],
                value=self.plot_states[self.current_plot_index].ystat,
                label="Y stat (grouped)",
                on_change=self._on_any_change,
            ).classes("w-full")

            self._abs_value_checkbox = ui.checkbox(
                "Absolute Value",
                value=self.plot_states[self.current_plot_index].use_absolute_value,
                on_change=self._on_any_change,
            ).classes("w-full")

            # Mean/Std/Sem controls (only for split_scatter and swarm)
            with ui.row().classes("w-full gap-2 items-center"):
                self._show_mean_checkbox = ui.checkbox(
                    "Mean",
                    value=self.plot_states[self.current_plot_index].show_mean,
                    on_change=self._on_any_change,
                )
                
                self._show_std_sem_checkbox = ui.checkbox(
                    "+/-",
                    value=self.plot_states[self.current_plot_index].show_std_sem,
                    on_change=self._on_any_change,
                )
                
                self._std_sem_select = ui.select(
                    options=["std", "sem"],
                    value=self.plot_states[self.current_plot_index].std_sem_type,
                    label="",
                    on_change=self._on_any_change,
                ).classes("flex-1")

            # X and Y column selection using aggrid
            with ui.row().classes("w-full gap-2 items-start"):
                # X column aggrid
                with ui.column().classes("flex-1"):
                    self._x_aggrid = self._create_column_aggrid("X column", self.plot_states[self.current_plot_index].xcol, self._on_x_column_selected)
                
                # Y column aggrid
                with ui.column().classes("flex-1"):
                    self._y_aggrid = self._create_column_aggrid("Y column", self.plot_states[self.current_plot_index].ycol, self._on_y_column_selected)

            ui.button("Replot", on_click=self._replot_current).classes("w-full")

            # Plot Options widget (modular and reusable)
            self._build_plot_options()

    def _build_plot_options(self) -> None:
        """Build modular plot options widget in a card container.
        
        This method creates a self-contained, reusable plot options widget
        that can be easily extracted and used in other projects.
        """
        with ui.card().classes("w-full mt-4"):
            ui.label("Plot Options").classes("text-lg font-semibold mb-2")
            
            with ui.column().classes("w-full gap-3"):
                # Mean and Error line widths in same row
                with ui.row().classes("w-full gap-2 items-center"):
                    self._mean_line_width_input = ui.number(
                        label="Mean Line Width",
                        value=self.plot_states[self.current_plot_index].mean_line_width,
                        min=1,
                        max=10,
                        step=1,
                        on_change=self._on_any_change,
                    ).classes("flex-1")
                    
                    self._error_line_width_input = ui.number(
                        label="Error Line Width",
                        value=self.plot_states[self.current_plot_index].error_line_width,
                        min=1,
                        max=10,
                        step=1,
                        on_change=self._on_any_change,
                    ).classes("flex-1")
                
                # Raw data and Point size in same row
                with ui.row().classes("w-full gap-2 items-center"):
                    self._show_raw_checkbox = ui.checkbox(
                        "Raw",
                        value=self.plot_states[self.current_plot_index].show_raw,
                        on_change=self._on_any_change,
                    )
                    
                    self._point_size_input = ui.number(
                        label="Point Size",
                        value=self.plot_states[self.current_plot_index].point_size,
                        min=1,
                        max=20,
                        step=1,
                        on_change=self._on_any_change,
                    ).classes("flex-1")
                
                # Legend
                self._show_legend_checkbox = ui.checkbox(
                    "Legend",
                    value=self.plot_states[self.current_plot_index].show_legend,
                    on_change=self._on_any_change,
                ).classes("w-full")

    def _rebuild_plot_panel(self) -> None:
        """Rebuild the plot panel based on current layout.
        
        Clears existing plots and recreates them in the new layout.
        This is necessary because NiceGUI doesn't support dynamic
        restructuring of widget containers.
        """
        if self._plot_container is None:
            return
        
        # Clear all existing plot widgets from the container
        self._plot_container.clear()
        
        # Parse layout string (e.g., "1x2" -> rows=1, cols=2)
        rows, cols = map(int, self.layout.split('x'))
        
        # Initialize plot widgets list
        self._plots = []
        
        # Create layout based on rows/cols
        if rows == 1 and cols == 1:
            # 1x1: Single plot
            with self._plot_container:
                with ui.column().classes("w-full h-full min-h-0 p-4"):
                    plot = ui.plotly(
                        self._make_figure_dict(self.plot_states[0])
                    ).classes("w-full h-full")
                    plot.on("plotly_click", lambda e, idx=0: self._on_plotly_click(e, plot_index=idx))
                    self._plots.append(plot)
        
        elif rows == 1 and cols == 2:
            # 2x1: Two plots side by side
            with self._plot_container:
                with ui.row().classes("w-full h-full gap-2"):
                    for i in range(2):
                        with ui.column().classes("flex-1 h-full min-h-0 p-4"):
                            plot = ui.plotly(
                                self._make_figure_dict(self.plot_states[i])
                            ).classes("w-full h-full")
                            plot.on("plotly_click", lambda e, idx=i: self._on_plotly_click(e, plot_index=idx))
                            self._plots.append(plot)
        
        elif rows == 2 and cols == 1:
            # 1x2: Two plots stacked vertically
            with self._plot_container:
                with ui.column().classes("w-full h-full gap-2"):
                    for i in range(2):
                        with ui.column().classes("w-full flex-1 min-h-0 p-4"):
                            plot = ui.plotly(
                                self._make_figure_dict(self.plot_states[i])
                            ).classes("w-full h-full")
                            plot.on("plotly_click", lambda e, idx=i: self._on_plotly_click(e, plot_index=idx))
                            self._plots.append(plot)

    # ----------------------------
    # UI Helpers
    # ----------------------------

    def _create_column_aggrid(self, label: str, initial_value: str, on_selected_callback) -> ui.aggrid:
        """Create an aggrid for column selection.
        
        Args:
            label: Label for the aggrid
            initial_value: Initial selected column name
            on_selected_callback: Callback function(row_dict) when row is selected
            
        Returns:
            ui.aggrid instance with single row selection enabled
        """
        # Create row data: one row per column in the dataframe
        # Convert to list explicitly to ensure it's a Python list, not pandas Index
        column_names = list(self.df.columns)
        row_data = [{"column": str(col)} for col in column_names]
        
        # Debug: log if row_data is empty
        if not row_data:
            logger.warning(
                f"Warning: No columns found in dataframe for {label} aggrid. "
                f"df has {len(self.df)} rows and {len(self.df.columns)} columns"
            )
        else:
            logger.debug(
                f"Created {len(row_data)} rows for {label} aggrid: "
                f"{[r['column'] for r in row_data[:5]]}..."
            )
        
        # Column definition: single column showing column names
        column_defs = [
            {
                "headerName": label,
                "field": "column",
                "sortable": True,
                "resizable": True,
            }
        ]
        
        # Grid options with single row selection
        # Reference: https://nicegui.io/documentation/aggrid
        # Format matches working examples from codebase (e.g., demo_aggrid_lazy_updates_v4.py)
        grid_options: dict[str, Any] = {
            "columnDefs": column_defs,
            "rowData": row_data,  # Must be a list of dicts
            "rowSelection": "single",  # Enable single row selection
            "rowHeight": 22,  # Compact row height (default is ~28px)
            "headerHeight": 26,  # Compact header height (default is ~30px)
            "defaultColDef": {
                "sortable": True,
                "resizable": True,
            },
        }
        
        # Add getRowId for programmatic selection by column name
        # Use ":" prefix for JS arrow function (NiceGUI v3.7+ requirement for JS expressions)
        # This enables run_row_method(column_name, "setSelected", ...) to work
        grid_options[":getRowId"] = "(params) => String(params.data.column)"
        
        # Ensure compact CSS is injected
        _ensure_aggrid_compact_css()
        
        # Create aggrid with compact styling class
        aggrid = ui.aggrid(grid_options).classes("w-full aggrid-compact")
        aggrid.style("height: 200px")
        
        # Wire up row selection event
        async def on_row_selected(e: GenericEventArguments) -> None:
            """Handle row selection event by fetching selected row asynchronously."""
            try:
                selected_row = await aggrid.get_selected_row()
                if selected_row:
                    column_name = selected_row.get("column")
                    if column_name:
                        logger.debug(f"{label} row selected: {column_name}")
                        on_selected_callback(selected_row)
                    else:
                        logger.warning(f"{label} selected row missing 'column' field: {selected_row}")
                else:
                    logger.debug(f"{label} row selection event but no row selected")
            except Exception as ex:
                logger.exception(f"Error handling {label} row selection: {ex}")
        
        aggrid.on("rowSelected", on_row_selected)
        
        # Set initial selection using run_row_method (requires getRowId to be set)
        # Use a timer to ensure grid is ready before selecting
        if initial_value:
            def set_initial_selection() -> None:
                try:
                    aggrid.run_row_method(initial_value, "setSelected", True, True)
                except Exception:
                    # Grid may not be ready yet, ignore
                    pass
            
            ui.timer(0.1, set_initial_selection, once=True)
        
        return aggrid

    # ----------------------------
    # Events
    # ----------------------------

    def _on_layout_change(self, layout_str: str) -> None:
        """Handle layout change (1x1, 1x2, 2x1).
        
        Args:
            layout_str: Layout string like "1x1", "1x2", "2x1".
        """
        logger.info(f"Layout changed to: {layout_str}")
        # Save current plot state before changing layout
        self.plot_states[self.current_plot_index] = self._widgets_to_state()
        self.layout = layout_str
        self._rebuild_plot_panel()
    
    def _on_plot_selection_change(self, plot_index: int) -> None:
        """Handle plot selection change (switch which plot is being edited).
        
        Args:
            plot_index: Index of plot to switch to (0-based).
        """
        logger.info(f"Switching to plot {plot_index + 1}")
        # Save current plot state
        self.plot_states[self.current_plot_index] = self._widgets_to_state()
        # Update current index
        self.current_plot_index = plot_index
        # Load new plot state into widgets (no replot needed)
        self._state_to_widgets(self.plot_states[self.current_plot_index])
    
    def _apply_current_to_others(self) -> None:
        """Apply current plot's state to all other plots."""
        logger.info("Applying current plot state to all other plots")
        # Get current state from widgets
        current_state = self._widgets_to_state()
        self.plot_states[self.current_plot_index] = current_state
        
        # Copy to all other plots
        for i in range(len(self.plot_states)):
            if i != self.current_plot_index:
                # Deep copy using serialization
                self.plot_states[i] = PlotState.from_dict(current_state.to_dict())
        
        # Replot all visible plots
        self._replot_all()

    def _on_x_column_selected(self, row_dict: dict[str, Any]) -> None:
        """Callback when X column is selected in aggrid."""
        column_name = row_dict.get("column")
        if column_name:
            logger.info(f"X column selected: {column_name}")
            self.plot_states[self.current_plot_index].xcol = str(column_name)
            self._on_any_change()
        else:
            logger.warning(f"X column selection callback received invalid row_dict: {row_dict}")

    def _on_y_column_selected(self, row_dict: dict[str, Any]) -> None:
        """Callback when Y column is selected in aggrid."""
        column_name = row_dict.get("column")
        if column_name:
            logger.info(f"Y column selected: {column_name}")
            self.plot_states[self.current_plot_index].ycol = str(column_name)
            self._on_any_change()
        else:
            logger.warning(f"Y column selection callback received invalid row_dict: {row_dict}")

    def _on_any_change(self, _e=None) -> None:
        """Handle changes to any control widget and trigger replot."""
        assert (
            self._roi_select and self._type_select and self._group_select 
            and self._ystat_select and self._abs_value_checkbox
            and self._show_mean_checkbox and self._show_std_sem_checkbox and self._std_sem_select
            and self._mean_line_width_input and self._error_line_width_input and self._show_raw_checkbox
            and self._point_size_input and self._show_legend_checkbox
        )

        logger.debug("Control change detected, updating state and replotting")
        
        # Update state from widgets (preserve xcol/ycol from aggrid)
        new_state = self._widgets_to_state()
        # Preserve xcol/ycol from current state (aggrid updates are async)
        new_state.xcol = self.plot_states[self.current_plot_index].xcol
        new_state.ycol = self.plot_states[self.current_plot_index].ycol
        
        # Save to current plot state
        self.plot_states[self.current_plot_index] = new_state

        logger.debug(
            f"State updated for plot {self.current_plot_index + 1}: roi_id={new_state.roi_id}, plot_type={new_state.plot_type.value}, "
            f"xcol={new_state.xcol}, ycol={new_state.ycol}, group_col={new_state.group_col}, "
            f"use_absolute_value={new_state.use_absolute_value}, "
            f"show_mean={new_state.show_mean}, show_std_sem={new_state.show_std_sem}, "
            f"std_sem_type={new_state.std_sem_type}, "
            f"mean_line_width={new_state.mean_line_width}, error_line_width={new_state.error_line_width}, "
            f"show_raw={new_state.show_raw}, point_size={new_state.point_size}, show_legend={new_state.show_legend}"
        )

        self._sync_controls()
        self._replot_current()

    def _sync_controls(self) -> None:
        """Enable/disable controls based on current plot type."""
        assert self._group_select and self._ystat_select
        assert self._show_mean_checkbox and self._show_std_sem_checkbox and self._std_sem_select
        
        state = self.plot_states[self.current_plot_index]
        needs_group = state.plot_type in {
            PlotType.GROUPED, 
            PlotType.SPLIT_SCATTER, 
            PlotType.SWARM,
            PlotType.CUMULATIVE_HISTOGRAM,
        }
        is_grouped_agg = state.plot_type == PlotType.GROUPED
        show_mean_std = state.plot_type in {PlotType.SPLIT_SCATTER, PlotType.SWARM}
        
        self._group_select.set_enabled(needs_group)
        self._ystat_select.set_enabled(is_grouped_agg)
        self._show_mean_checkbox.set_enabled(show_mean_std)
        self._show_std_sem_checkbox.set_enabled(show_mean_std)
        self._std_sem_select.set_enabled(show_mean_std and state.show_std_sem)
        
        logger.debug(
            f"Controls synced: group_select enabled={needs_group}, "
            f"ystat_select enabled={is_grouped_agg}, "
            f"mean/std controls enabled={show_mean_std}"
        )

    def _on_plotly_click(self, e: GenericEventArguments, plot_index: int = 0) -> None:
        """Handle click events on the Plotly plot.
        
        Args:
            e: Event arguments from Plotly click.
            plot_index: Index of the plot that was clicked (0-based).
        """
        points = (e.args or {}).get("points") or []
        if not points:
            logger.debug("Plotly click event received but no points found")
            return

        p0: dict[str, Any] = points[0]
        custom = p0.get("customdata")
        state = self.plot_states[plot_index]

        # per-row plots: click -> row_id -> filtered df row
        if state.plot_type in {PlotType.SCATTER, PlotType.SPLIT_SCATTER, PlotType.SWARM}:
            row_id: Optional[str] = None
            if isinstance(custom, (str, int, float)):
                row_id = str(custom)
            elif isinstance(custom, (list, tuple)) and custom:
                row_id = str(custom[0])

            if not row_id:
                logger.debug(f"Could not extract row_id from plotly click: custom={custom}")
                return

            logger.info(f"Plotly click on plot {plot_index + 1}: plot_type={state.plot_type.value}, row_id={row_id}")

            df_f = self.data_processor.filter_by_roi(state.roi_id)
            idx = self._id_to_index_filtered.get(row_id)
            if idx is None:
                logger.warning(f"Row ID {row_id} not found in filtered index")
                return

            row = df_f.iloc[idx]
            if self._clicked_label:
                self._clicked_label.text = f"Plot {plot_index + 1}: ROI={state.roi_id} \n {self.row_id_col}={row_id} \n (filtered iloc={idx})"
            logger.info(f"Clicked row data: {row.to_dict()}")
            pprint(row.to_dict())
            return

        # grouped aggregation plot: click -> group summary
        if state.plot_type == PlotType.GROUPED:
            x = p0.get("x")
            y = p0.get("y")
            logger.info(f"Plotly click on plot {plot_index + 1} grouped plot: group={x}, y={y}")
            if self._clicked_label:
                self._clicked_label.text = f"Plot {plot_index + 1}: ROI={state.roi_id} clicked group={x}, y={y} (aggregated)"
            return

    # ----------------------------
    # Plotting
    # ----------------------------

    def _replot_current(self) -> None:
        """Update the current plot with its state and data."""
        if not self._plots or self.current_plot_index >= len(self._plots):
            return
        logger.debug(f"Replotting plot {self.current_plot_index + 1}")
        state = self.plot_states[self.current_plot_index]
        self._plots[self.current_plot_index].update_figure(self._make_figure_dict(state))
    
    def _replot_all(self) -> None:
        """Replot all visible plots based on current layout."""
        rows, cols = map(int, self.layout.split('x'))
        num_plots = rows * cols
        
        for i in range(min(num_plots, len(self._plots), len(self.plot_states))):
            state = self.plot_states[i]
            self._plots[i].update_figure(self._make_figure_dict(state))

    def _make_figure_dict(self, state: PlotState) -> dict:
        """Generate Plotly figure dictionary based on plot state.
        
        Args:
            state: PlotState to use for generating the figure.
            
        Returns:
            Plotly figure dictionary.
        """
        df_f = self.data_processor.filter_by_roi(state.roi_id)
        self._id_to_index_filtered = self.data_processor.build_row_id_index(df_f)

        logger.debug(f"Making figure: plot_type={state.plot_type.value}, filtered_rows={len(df_f)}")

        if state.plot_type == PlotType.GROUPED:
            return self._figure_grouped(df_f, state)
        if state.plot_type == PlotType.SPLIT_SCATTER:
            return self._figure_split_scatter(df_f, state)
        if state.plot_type == PlotType.SWARM:
            return self._figure_swarm(df_f, state)
        if state.plot_type == PlotType.CUMULATIVE_HISTOGRAM:
            return self._figure_cumulative_histogram(df_f, state)
        return self._figure_scatter(df_f, state)

    def _figure_scatter(self, df_f: pd.DataFrame, state: PlotState) -> dict:
        """Create scatter plot figure.
        
        Args:
            df_f: Filtered dataframe.
            state: PlotState to use for configuration.
        """
        x = df_f[state.xcol]
        y = self.data_processor.get_y_values(df_f, state.ycol, state.use_absolute_value)
        row_ids = df_f[self.row_id_col].astype(str)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode="markers",
            name=f"ROI {state.roi_id}",
            customdata=row_ids,
            marker=dict(size=state.point_size),
            hovertemplate=(
                # f"roi_id={state.roi_id}<br>"
                f"{state.xcol}=%{{x}}<br>"
                f"{state.ycol}=%{{y}}<br>"
                # f"{self.row_id_col}=%{{customdata}}<extra></extra>"
            ),
        ))
        fig.update_layout(
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis_title=state.xcol,
            yaxis_title=state.ycol,
            showlegend=state.show_legend,
            uirevision="keep",
        )
        return fig.to_dict()

    def _figure_split_scatter(self, df_f: pd.DataFrame, state: PlotState) -> dict:
        """Create split scatter plot with color coding by group column.
        
        Args:
            df_f: Filtered dataframe.
            state: PlotState to use for configuration.
        """
        if not state.group_col:
            return self._figure_scatter(df_f, state)

        x = df_f[state.xcol]
        y = self.data_processor.get_y_values(df_f, state.ycol, state.use_absolute_value)
        g = df_f[state.group_col].astype(str)
        row_ids = df_f[self.row_id_col].astype(str)

        tmp = pd.DataFrame({"x": x, "y": y, "g": g, "row_id": row_ids}).dropna(subset=["g"])
        fig = go.Figure()

        # Calculate y-axis range from raw data (for preserving range when show_raw is off)
        y_min_raw = float(tmp["y"].min()) if len(tmp) > 0 else None
        y_max_raw = float(tmp["y"].max()) if len(tmp) > 0 else None

        # Calculate x ranges for each group (for mean/std positioning)
        # Handle both numeric and string x columns
        x_ranges = {}
        for group_value, sub in tmp.groupby("g", sort=True):
            x_min = sub["x"].min()
            x_max = sub["x"].max()
            # Try to convert to float, but allow strings for categorical x columns
            try:
                x_min_val = float(x_min)
                x_max_val = float(x_max)
            except (ValueError, TypeError):
                # For string columns, use 0-based positions or string comparison
                # For mean/std positioning, we'll use a simple range
                # In practice, mean/std won't be meaningful for string x, but we need a range
                x_min_val = 0.0
                x_max_val = 1.0
            x_ranges[str(group_value)] = (x_min_val, x_max_val)
            # Only add raw data trace if show_raw is True
            if state.show_raw:
                fig.add_trace(go.Scatter(
                    x=sub["x"],
                    y=sub["y"],
                    mode="markers",
                    name=str(group_value),
                    customdata=sub["row_id"],
                    marker=dict(size=state.point_size),
                    hovertemplate=(
                        # f"roi_id={state.roi_id}<br>"
                        f"{state.group_col}={group_value}<br>"
                        f"{state.xcol}=%{{x}}<br>"
                        f"{state.ycol}=%{{y}}<br>"
                        # f"{self.row_id_col}=%{{customdata}}<extra></extra>"
                    ),
                ))

        # Add mean and std/sem traces if enabled (include x-axis stats for split_scatter)
        if state.show_mean or state.show_std_sem:
            group_stats = self.data_processor.calculate_group_stats(
                df_f, state.group_col, state.ycol, state.use_absolute_value,
                state.xcol, include_x=True
            )
            self._add_mean_std_traces(fig, group_stats, x_ranges, state, include_x_axis=True)

        # Preserve y-axis range when show_raw is off
        layout_updates = {
            "margin": dict(l=40, r=20, t=40, b=40),
            "xaxis_title": state.xcol,
            "yaxis_title": state.ycol,
            "legend_title_text": state.group_col,
            "showlegend": state.show_legend,
            "uirevision": "keep",
        }
        
        # If show_raw is off, preserve y-axis range from raw data
        # If show_raw is on, auto-scale y-axis (remove any fixed range)
        if not state.show_raw and y_min_raw is not None and y_max_raw is not None:
            # Add some padding
            y_padding = (y_max_raw - y_min_raw) * 0.1 if y_max_raw != y_min_raw else abs(y_max_raw) * 0.1 if y_max_raw != 0 else 1.0
            layout_updates["yaxis"] = dict(range=[y_min_raw - y_padding, y_max_raw + y_padding])
        else:
            # When show_raw is True, explicitly set yaxis to auto-scale
            layout_updates["yaxis"] = dict(autorange=True)
        
        fig.update_layout(**layout_updates)
        return fig.to_dict()

    def _figure_swarm(self, df_f: pd.DataFrame, state: PlotState) -> dict:
        """Create swarm/strip plot with optional group coloring.
        
        Uses manual jitter by converting categorical x values to numeric positions
        and adding random horizontal offsets, similar to the demo_jitter.py pattern.
        
        Args:
            df_f: Filtered dataframe.
            state: PlotState to use for configuration.
        """
        # x is categorical bins, y is per-row; optional color split via group_col
        x_cat = df_f[state.xcol].astype(str)
        y = self.data_processor.get_y_values(df_f, state.ycol, state.use_absolute_value)
        row_ids = df_f[self.row_id_col].astype(str)

        # Get unique categorical values and create mapping to numeric positions
        unique_cats = sorted(x_cat.unique())
        cat_to_pos = {cat: i for i, cat in enumerate(unique_cats)}
        
        # Jitter parameters
        jitter_amount = 0.35  # Horizontal spread within each category
        
        fig = go.Figure()

        if state.group_col:
            g = df_f[state.group_col].astype(str)
            tmp = pd.DataFrame({"x": x_cat, "y": y, "g": g, "row_id": row_ids}).dropna(subset=["x"])
            
            # Calculate y-axis range from raw data (for preserving range when show_raw is off)
            y_min_raw = float(tmp["y"].min()) if len(tmp) > 0 else None
            y_max_raw = float(tmp["y"].max()) if len(tmp) > 0 else None
            
            # Calculate x ranges for each group (for mean/std positioning)
            # For swarm plots, x is categorical, so we use the category position
            x_ranges = {}
            
            for gv, sub in tmp.groupby("g", sort=True):
                # Convert categorical x to numeric positions
                x_positions = sub["x"].map(cat_to_pos).values
                # Add jitter: random offset between -jitter_amount/2 and +jitter_amount/2
                # Use hash of group value for seed to get different jitter per group
                seed = hash(str(gv)) % (2**31)
                rng = np.random.default_rng(seed=seed)
                jitter = rng.uniform(-jitter_amount/2, jitter_amount/2, size=len(x_positions))
                x_jittered = x_positions + jitter
                
                # Store x range for this group (center position ± jitter range)
                # For swarm, we need to calculate per category, but for simplicity,
                # we'll use the mean x position across all categories for this group
                x_center = float(np.mean(x_positions))
                x_ranges[str(gv)] = (x_center - jitter_amount/2, x_center + jitter_amount/2)
                
                # Store original categorical x and row_id for hover
                x_cat_values = sub["x"].values
                row_id_values = sub["row_id"].values
                
                # Only add raw data trace if show_raw is True
                if state.show_raw:
                    fig.add_trace(go.Scatter(
                        x=x_jittered,
                        y=sub["y"].values,
                        mode="markers",
                        name=str(gv),
                        customdata=np.column_stack([x_cat_values, row_id_values]),
                        marker=dict(size=state.point_size),
                        hovertemplate=(
                            # f"roi_id={state.roi_id}<br>"
                            f"{state.xcol}=%{{customdata[0]}}<br>"
                            f"{state.ycol}=%{{y}}<br>"
                            f"{state.group_col}={gv}<br>"
                            # f"{self.row_id_col}=%{{customdata[1]}}<extra></extra>"
                        ),
                    ))
            
            # Add mean and std/sem traces if enabled (only y-axis for swarm)
            if state.show_mean or state.show_std_sem:
                group_stats = self.data_processor.calculate_group_stats(
                    df_f, state.group_col, state.ycol, state.use_absolute_value,
                    None, include_x=False
                )
                self._add_mean_std_traces(fig, group_stats, x_ranges, state, include_x_axis=False)
        else:
            tmp = pd.DataFrame({"x": x_cat, "y": y, "row_id": row_ids}).dropna(subset=["x"])
            
            # Calculate y-axis range from raw data (for preserving range when show_raw is off)
            y_min_raw = float(tmp["y"].min()) if len(tmp) > 0 else None
            y_max_raw = float(tmp["y"].max()) if len(tmp) > 0 else None
            
            # Convert categorical x to numeric positions
            x_positions = tmp["x"].map(cat_to_pos).values
            # Add jitter: random offset between -jitter_amount/2 and +jitter_amount/2
            rng = np.random.default_rng(seed=42)  # Fixed seed for reproducibility
            jitter = rng.uniform(-jitter_amount/2, jitter_amount/2, size=len(x_positions))
            x_jittered = x_positions + jitter
            
            # Store original categorical x and row_id for hover
            x_cat_values = tmp["x"].values
            row_id_values = tmp["row_id"].values
            
            # Only add raw data trace if show_raw is True
            if state.show_raw:
                fig.add_trace(go.Scatter(
                    x=x_jittered,
                    y=tmp["y"].values,
                    mode="markers",
                    name=f"ROI {state.roi_id}",
                    customdata=np.column_stack([x_cat_values, row_id_values]),
                    marker=dict(size=state.point_size),
                    hovertemplate=(
                        # f"roi_id={state.roi_id}<br>"
                        f"{state.xcol}=%{{customdata[0]}}<br>"
                        f"{state.ycol}=%{{y}}<br>"
                        # f"{self.row_id_col}=%{{customdata[1]}}<extra></extra>"
                    ),
                ))

        # Set up x-axis with categorical labels at integer positions
        layout_updates = {
            "margin": dict(l=40, r=20, t=40, b=90),
            "xaxis_title": state.xcol,
            "yaxis_title": state.ycol,
            "showlegend": state.show_legend,
            "xaxis": dict(
                tickmode="array",
                tickvals=list(range(len(unique_cats))),
                ticktext=unique_cats,
                tickangle=-30,
            ),
            "uirevision": "keep",
        }
        
        # Preserve y-axis range when show_raw is off (for both grouped and ungrouped swarm)
        # If show_raw is on, auto-scale y-axis (remove any fixed range)
        if not state.show_raw:
            if state.group_col:
                # Use the y_min_raw and y_max_raw calculated above
                if y_min_raw is not None and y_max_raw is not None:
                    y_padding = (y_max_raw - y_min_raw) * 0.1 if y_max_raw != y_min_raw else abs(y_max_raw) * 0.1 if y_max_raw != 0 else 1.0
                    layout_updates["yaxis"] = dict(range=[y_min_raw - y_padding, y_max_raw + y_padding])
            else:
                # Ungrouped case
                if y_min_raw is not None and y_max_raw is not None:
                    y_padding = (y_max_raw - y_min_raw) * 0.1 if y_max_raw != y_min_raw else abs(y_max_raw) * 0.1 if y_max_raw != 0 else 1.0
                    layout_updates["yaxis"] = dict(range=[y_min_raw - y_padding, y_max_raw + y_padding])
        else:
            # When show_raw is True, explicitly set yaxis to auto-scale
            layout_updates["yaxis"] = dict(autorange=True)
        
        fig.update_layout(**layout_updates)
        return fig.to_dict()

    def _figure_grouped(self, df_f: pd.DataFrame, state: PlotState) -> dict:
        """Create grouped aggregation plot showing statistics by group.
        
        Args:
            df_f: Filtered dataframe.
            state: PlotState to use for configuration.
        """
        if not state.group_col:
            return self._figure_scatter(df_f, state)

        g = df_f[state.group_col].astype(str)
        y = self.data_processor.get_y_values(df_f, state.ycol, state.use_absolute_value)
        tmp = pd.DataFrame({"group": g, "y": y}).dropna(subset=["group"])

        stat = state.ystat
        if stat == "count":
            agg = tmp.groupby("group", dropna=False)["y"].count()
        else:
            # y is already numeric from get_y_values, but ensure it's numeric for aggregation
            tmp["y"] = pd.to_numeric(tmp["y"], errors="coerce")
            agg = getattr(tmp.groupby("group", dropna=False)["y"], stat)()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=agg.index.astype(str).tolist(),
            y=agg.values.tolist(),
            mode="markers+lines",
            name=f"ROI {state.roi_id}",
        ))
        fig.update_layout(
            margin=dict(l=40, r=20, t=40, b=80),
            xaxis_title=state.group_col,
            yaxis_title=f"{stat}({state.ycol})",
            xaxis_tickangle=-30,
            showlegend=state.show_legend,
            uirevision="keep",
        )
        return fig.to_dict()

    def _figure_cumulative_histogram(self, df_f: pd.DataFrame, state: PlotState) -> dict:
        """Create cumulative histogram plot with one curve per group.
        
        For each unique value in group_col, computes a cumulative histogram
        of x values, normalized to 0-1 range within each category.
        
        Args:
            df_f: Filtered dataframe.
            state: PlotState to use for configuration.
        """
        if not state.group_col:
            logger.warning("Cumulative histogram requires a group/color column. Falling back to scatter plot.")
            return self._figure_scatter(df_f, state)

        x = pd.to_numeric(df_f[state.xcol], errors="coerce")
        g = df_f[state.group_col].astype(str)
        
        # Drop rows with missing x or group values
        tmp = pd.DataFrame({"x": x, "g": g}).dropna(subset=["x", "g"])
        
        if len(tmp) == 0:
            logger.warning("No valid data for cumulative histogram. Falling back to scatter plot.")
            return self._figure_scatter(df_f)

        logger.warning(
            "Cumulative histogram: normalizing each category's cumulative distribution to 0-1 range. "
            "This means the y-axis represents the cumulative proportion within each category, not absolute counts."
        )

        fig = go.Figure()

        # Number of bins for histogram
        n_bins = 50
        
        for group_value, sub in tmp.groupby("g", sort=True):
            x_values = sub["x"].values
            
            if len(x_values) == 0:
                continue
            
            # Compute histogram
            counts, bin_edges = np.histogram(x_values, bins=n_bins)
            
            # Compute cumulative sum
            cumsum = np.cumsum(counts)
            
            # Normalize to 0-1 range
            if cumsum[-1] > 0:
                cumsum_normalized = cumsum / cumsum[-1]
            else:
                cumsum_normalized = cumsum
            
            # Add step line trace for cumulative histogram
            # We need to add the first point at the start of the first bin
            x_plot = np.concatenate([[bin_edges[0]], bin_edges[1:]])
            y_plot = np.concatenate([[0], cumsum_normalized])
            
            fig.add_trace(go.Scatter(
                x=x_plot,
                y=y_plot,
                mode="lines",
                name=str(group_value),
                line=dict(shape="hv"),  # Step line (horizontal-vertical)
                hovertemplate=(
                    f"{state.group_col}={group_value}<br>"
                    f"{state.xcol}=%{{x}}<br>"
                    f"Cumulative proportion=%{{y:.3f}}<extra></extra>"
                ),
            ))

        fig.update_layout(
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis_title=state.xcol,
            yaxis_title="Cumulative Proportion (normalized 0-1)",
            legend_title_text=state.group_col,
            showlegend=state.show_legend,
            uirevision="keep",
        )
        return fig.to_dict()


# ----------------------------
# Demo entrypoint
# ----------------------------

def main() -> None:
    """Demo entrypoint: load data and launch the plot controller UI."""

    path = '/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v1-analysis/radon_report.csv'
    df = pd.read_csv(path)

    # print(df.head())

    _setUpGuiDefaults()
    
    ui.page_title("NiceGUI + Plotly (ROI filter + click row)")
    # ui.label("Filter by ROI, replot, and click points to print the filtered df row.").classes("text-lg font-medium")

    ctrl = PlotController(df, roi_id_col="roi_id", row_id_col="path")
    ctrl.build()

    native_bool = True
    reload_bool = True
    ui.run(reload=reload_bool,
            native=native_bool,
            window_size=(1000, 800))


if __name__ in {"__main__", "__mp_main__"}:
    main()