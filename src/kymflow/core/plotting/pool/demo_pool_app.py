# app.py
from __future__ import annotations

from typing import Any, Optional

from pprint import pprint
import numpy as np
import pandas as pd
from nicegui import ui
from nicegui.events import GenericEventArguments

from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.gui_v2.app_context import _setUpGuiDefaults
from kymflow.core.plotting.pool.plot_state import PlotType, PlotState
from kymflow.core.plotting.pool.plot_helpers import (
    numeric_columns,
    categorical_candidates,
    _ensure_aggrid_compact_css,
    points_in_polygon,
    parse_plotly_path_to_xy,
)
from kymflow.core.plotting.pool.dataframe_processor import DataFrameProcessor
from kymflow.core.plotting.pool.figure_generator import FigureGenerator

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

        # Initialize FigureGenerator for plot generation
        self.figure_generator = FigureGenerator(
            self.data_processor,
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
        self._last_plot_type: Optional[PlotType] = None  # Track plot type changes for forced rebuild
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
        # Linked selection: set of row_ids selected in any plot; applied to all compatible plots
        self._selected_row_ids: set[str] = set()
        # When True, next rect/lasso selection will be added to current selection (Cmd/Ctrl + select)
        self._extend_selection_modifier: bool = False
        # UI: label showing selection count (updated when selection changes)
        self._selection_label: Optional[ui.label] = None

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



    # ----------------------------
    # UI
    # ----------------------------

    def build(self) -> None:
        """Build the main UI layout with header, splitter, controls, and plot."""
        # Header area at the top
        with ui.column().classes("w-full"):
            ui.label("Radon Analysis Pool Plot").classes("text-2xl font-bold mb-2")
            with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                self._clicked_label = ui.label("Click a point to show the filtered df row...").classes("text-sm text-gray-600")
                self._selection_label = ui.label("No selection").classes("text-sm font-medium")
                ui.button("Clear selection", on_click=self._clear_selection).classes("text-sm")
            # Global Esc to clear selection (NiceGUI keyboard element)
            ui.keyboard(on_key=self._on_keyboard_key)
        
        # Main splitter: horizontal layout with controls on left, plot on right
        # on_change: when user resizes splitter, re-build plot panel so 1x2/2x1 layout is not lost
        # (NiceGUI/Quasar can re-render the 'after' slot and show only one plot; rebuild restores correct count)
        self._mainSplitter = ui.splitter(
            value=25,
            limits=(15, 50),
            on_change=lambda _: self._on_splitter_change(),
        ).classes("w-full h-screen")
        
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
        self._update_selection_label()

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
                        self._make_figure_dict(self.plot_states[0], selected_row_ids=None)
                    ).classes("w-full h-full")
                    plot.on("plotly_click", lambda e, idx=0: self._on_plotly_click(e, plot_index=idx))
                    if self._is_selection_compatible(self.plot_states[0].plot_type):
                        plot.on("plotly_relayout", lambda e, idx=0: self._on_plotly_relayout(e, plot_index=idx))
                    self._plots.append(plot)
        
        elif rows == 1 and cols == 2:
            # 2x1: Two plots side by side
            with self._plot_container:
                with ui.row().classes("w-full h-full gap-2"):
                    for i in range(2):
                        with ui.column().classes("flex-1 h-full min-h-0 p-4"):
                            plot = ui.plotly(
                                self._make_figure_dict(self.plot_states[i], selected_row_ids=None)
                            ).classes("w-full h-full")
                            plot.on("plotly_click", lambda e, idx=i: self._on_plotly_click(e, plot_index=idx))
                            if self._is_selection_compatible(self.plot_states[i].plot_type):
                                plot.on("plotly_relayout", lambda e, idx=i: self._on_plotly_relayout(e, plot_index=idx))
                            self._plots.append(plot)
        
        elif rows == 2 and cols == 1:
            # 1x2: Two plots stacked vertically
            with self._plot_container:
                with ui.column().classes("w-full h-full gap-2"):
                    for i in range(2):
                        with ui.column().classes("w-full flex-1 min-h-0 p-4"):
                            plot = ui.plotly(
                                self._make_figure_dict(self.plot_states[i], selected_row_ids=None)
                            ).classes("w-full h-full")
                            plot.on("plotly_click", lambda e, idx=i: self._on_plotly_click(e, plot_index=idx))
                            if self._is_selection_compatible(self.plot_states[i].plot_type):
                                plot.on("plotly_relayout", lambda e, idx=i: self._on_plotly_relayout(e, plot_index=idx))
                            self._plots.append(plot)
        
        # Initialize last plot type tracking after plots are created
        if self._plots and self._last_plot_type is None:
            self._last_plot_type = self.plot_states[self.current_plot_index].plot_type

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

    def _on_splitter_change(self) -> None:
        """Restore plot panel after splitter resize (avoids 1x2/2x1 collapsing to single plot)."""
        self._rebuild_plot_panel()

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

        logger.info("Control change detected, updating state and replotting")
        
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

    def _is_selection_compatible(self, plot_type: PlotType) -> bool:
        """Check if plot type supports point selection (rect/lasso).
        
        Args:
            plot_type: PlotType to check.
            
        Returns:
            True if plot type supports selection, False otherwise.
        """
        SELECTION_COMPATIBLE_TYPES = {
            PlotType.SCATTER,
            PlotType.SPLIT_SCATTER,
            PlotType.SWARM,
        }
        return plot_type in SELECTION_COMPATIBLE_TYPES

    def _update_selection_label(self) -> None:
        """Update the header label to show number of selected points or 'No selection'."""
        if self._selection_label is None:
            return
        n = len(self._selected_row_ids)
        self._selection_label.text = f"{n} points selected" if n else "No selection"

    def _clear_selection(self) -> None:
        """Clear linked selection and refresh all compatible plots."""
        if not self._selected_row_ids:
            return
        self._selected_row_ids = set()
        self._apply_selection_to_all_plots()
        self._update_selection_label()
        logger.info("Selection cleared (Clear selection button)")

    def _on_keyboard_key(self, e) -> None:
        """Escape: clear selection. Cmd/Ctrl: set extend-selection flag for next rect/lasso."""
        key_name = getattr(getattr(e, "key", None), "name", None) if e else None
        if key_name == "Escape":
            if self._selected_row_ids:
                self._clear_selection()
                logger.info("Selection cleared (Esc)")
            return
        # Track Cmd (Meta) or Ctrl for extend selection: hold modifier, then draw rect/lasso to add to selection
        if key_name in ("Meta", "Control"):
            action = getattr(e, "action", None)
            if action and getattr(action, "keydown", False):
                self._extend_selection_modifier = True
            elif action and getattr(action, "keyup", False):
                self._extend_selection_modifier = False

    def _on_plotly_relayout(self, e: GenericEventArguments, plot_index: int = 0) -> None:
        """Handle plotly_relayout: get x/y range (rect) or path (lasso) from selections and compute selected rows.

        Relayout payload is small (no points array). We only process when payload contains
        layout.selections (user drew a rect or lasso). Rect: points in range. Lasso: path parsed to polygon.
        """
        raw = e.args
        if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], dict):
            payload = raw[0]
        elif isinstance(raw, dict):
            payload = raw
        else:
            payload = {}

        if "selections" not in payload:
            return
        selections = payload.get("selections") or []
        if not selections:
            # User cleared selection (e.g. double-click) — clear linked selection and refresh all plots
            if self._selected_row_ids:
                self._selected_row_ids = set()
                self._apply_selection_to_all_plots()
                self._update_selection_label()
            return

        state = self.plot_states[plot_index]
        if not self._is_selection_compatible(state.plot_type):
            return
        df_f = self.data_processor.filter_by_roi(state.roi_id)
        selected_row_ids: set[str] = set()
        source = "none"

        # Flattened keys (Plotly sometimes sends selections[0].x0 etc.)
        x0 = payload.get("selections[0].x0")
        x1 = payload.get("selections[0].x1")
        y0 = payload.get("selections[0].y0")
        y1 = payload.get("selections[0].y1")
        if x0 is not None and x1 is not None and y0 is not None and y1 is not None:
            try:
                x_range = (float(min(x0, x1)), float(max(x0, x1)))
                y_range = (float(min(y0, y1)), float(max(y0, y1)))
                selected_row_ids = self._compute_selected_points_from_range(
                    df_f, state, x_range=x_range, y_range=y_range
                )
                source = "rect"
            except (TypeError, ValueError):
                pass

        # Nested selections[0] with type 'rect' or 'path'
        if not selected_row_ids and selections:
            sel = selections[0] if isinstance(selections[0], dict) else None
            if sel:
                stype = sel.get("type")
                if stype == "rect":
                    try:
                        x0, x1 = sel.get("x0"), sel.get("x1")
                        y0, y1 = sel.get("y0"), sel.get("y1")
                        if x0 is not None and x1 is not None and y0 is not None and y1 is not None:
                            x_range = (float(min(x0, x1)), float(max(x0, x1)))
                            y_range = (float(min(y0, y1)), float(max(y0, y1)))
                            selected_row_ids = self._compute_selected_points_from_range(
                                df_f, state, x_range=x_range, y_range=y_range
                            )
                            source = "rect"
                    except (TypeError, ValueError):
                        pass
                elif stype == "path":
                    path_str = sel.get("path")
                    lasso_x, lasso_y = parse_plotly_path_to_xy(path_str or "")
                    if lasso_x and lasso_y and len(lasso_x) == len(lasso_y):
                        selected_row_ids = self._compute_selected_points_from_lasso(
                            df_f, state, lasso_x=lasso_x, lasso_y=lasso_y
                        )
                        source = "lasso"

        if not selected_row_ids:
            return
        # Extend selection: Cmd/Ctrl + rect or lasso adds to current (union); no double-count
        if self._extend_selection_modifier and self._selected_row_ids:
            self._selected_row_ids = self._selected_row_ids | selected_row_ids
            self._extend_selection_modifier = False  # one-shot: next selection without modifier replaces
            logger.info(
                f"Extend selection on plot {plot_index + 1}: source={source}, "
                f"added {len(selected_row_ids)}, total selected={len(self._selected_row_ids)}"
            )
        else:
            self._selected_row_ids = selected_row_ids
            logger.info(
                f"Selection on plot {plot_index + 1}: source={source}, "
                f"plot_type={state.plot_type.value}, selected_count={len(selected_row_ids)}, roi_id={state.roi_id}"
            )
        self._apply_selection_to_all_plots()
        self._update_selection_label()
        logger.debug(
            f"Selected row_ids: {sorted(list(selected_row_ids)[:10])}{'...' if len(selected_row_ids) > 10 else ''}"
        )

    def _apply_selection_to_all_plots(self) -> None:
        """Update all selection-compatible plots to show the current linked selection (_selected_row_ids)."""
        for i in range(len(self._plots)):
            if i >= len(self.plot_states):
                break
            if not self._is_selection_compatible(self.plot_states[i].plot_type):
                continue
            fig_dict = self._make_figure_dict(self.plot_states[i], selected_row_ids=self._selected_row_ids)
            self._plots[i].update_figure(fig_dict)
            self._plots[i].update()

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

    def _compute_selected_points_from_range(
        self,
        df_f: pd.DataFrame,
        state: PlotState,
        x_range: Optional[tuple[float, float]] = None,
        y_range: Optional[tuple[float, float]] = None,
    ) -> set[str]:
        """Compute selected row_ids from selection range/bbox (box select).

        Works for numeric and categorical x: uses FigureGenerator.get_axis_x_for_selection
        so that x is in the same axis space as the plot (category indices for categorical).
        """
        if not len(df_f):
            return set()
        x_axis = self.figure_generator.get_axis_x_for_selection(df_f, state)
        y_vals = self.data_processor.get_y_values(df_f, state.ycol, state.use_absolute_value)
        row_ids = df_f[self.row_id_col].astype(str)
        
        # Build mask: points inside bounding box [x_min, x_max] x [y_min, y_max]
        mask = pd.Series(True, index=df_f.index)
        if x_range is not None:
            x_min, x_max = x_range
            mask = mask & (x_axis >= x_min) & (x_axis <= x_max)
        if y_range is not None:
            y_min, y_max = y_range
            mask = mask & (y_vals >= y_min) & (y_vals <= y_max)
        
        return set(row_ids[mask].tolist())

    def _compute_selected_points_from_lasso(
        self,
        df_f: pd.DataFrame,
        state: PlotState,
        lasso_x: list[float],
        lasso_y: list[float],
    ) -> set[str]:
        """Compute selected row_ids from lasso polygon (point-in-polygon)."""
        if not len(df_f) or not lasso_x or not lasso_y or len(lasso_x) != len(lasso_y):
            return set()
        x_axis = self.figure_generator.get_axis_x_for_selection(df_f, state)
        y_vals = self.data_processor.get_y_values(df_f, state.ycol, state.use_absolute_value)
        points = np.column_stack([x_axis.values, y_vals.values])
        polygon_xy = np.column_stack([lasso_x, lasso_y])
        mask = points_in_polygon(points, polygon_xy)
        row_ids = df_f[self.row_id_col].astype(str)
        return set(row_ids.loc[mask].tolist())

    # ----------------------------
    # Plotting
    # ----------------------------

    def _replot_current(self) -> None:
        """Update the current plot with its state and data."""
        if not self._plots:
            logger.warning("Cannot replot: no plots available")
            return
        
        # Clamp current_plot_index to valid range based on actual number of plots
        if self.current_plot_index >= len(self._plots):
            logger.debug(f"Clamping current_plot_index from {self.current_plot_index} to {len(self._plots) - 1}")
            self.current_plot_index = len(self._plots) - 1
        
        state = self.plot_states[self.current_plot_index]
        
        # Check if plot type changed - if so, force a full rebuild
        plot_type_changed = (
            self._last_plot_type is not None and 
            self._last_plot_type != state.plot_type
        )
        
        logger.info(
            f"Replotting plot {self.current_plot_index + 1} - "
            f"plot_type={state.plot_type.value}, roi_id={state.roi_id}, "
            f"xcol={state.xcol}, ycol={state.ycol}, group_col={state.group_col}, "
            f"show_raw={state.show_raw}, show_legend={state.show_legend}, "
            f"plot_type_changed={plot_type_changed}"
        )
        
        try:
            figure_dict = self._make_figure_dict(state)
            logger.info(f"Figure dict created successfully with {len(figure_dict.get('data', []))} traces")
            
            # If plot type changed, force a full rebuild of the plot panel
            # This is necessary because update_figure() can be unreliable when plot structure changes significantly
            if plot_type_changed:
                logger.info(f"Plot type changed from {self._last_plot_type.value} to {state.plot_type.value}, forcing full rebuild")
                self._rebuild_plot_panel()
            else:
                # Normal update - just update the figure
                self._plots[self.current_plot_index].update_figure(figure_dict)
                # Explicitly call update() to ensure the change is applied
                self._plots[self.current_plot_index].update()
            
            # Update last plot type
            self._last_plot_type = state.plot_type
            
            logger.info(f"Plot {self.current_plot_index + 1} updated successfully")
        except Exception as ex:
            logger.exception(f"Error replotting plot {self.current_plot_index + 1}: {ex}")
    
    def _replot_all(self) -> None:
        """Replot all visible plots based on current layout."""
        rows, cols = map(int, self.layout.split('x'))
        num_plots = rows * cols
        
        for i in range(min(num_plots, len(self._plots), len(self.plot_states))):
            state = self.plot_states[i]
            self._plots[i].update_figure(
                self._make_figure_dict(state, selected_row_ids=self._selected_row_ids or None)
            )

    def _make_figure_dict(
        self,
        state: PlotState,
        *,
        selected_row_ids: Optional[set[str]] = None,
    ) -> dict:
        """Generate Plotly figure dictionary based on plot state.
        
        Args:
            state: PlotState to use for generating the figure.
            selected_row_ids: If set, these row_ids are shown as selected (linked selection).
            
        Returns:
            Plotly figure dictionary.
        """
        df_f = self.data_processor.filter_by_roi(state.roi_id)
        self._id_to_index_filtered = self.data_processor.build_row_id_index(df_f)
        
        logger.debug(f"Making figure: plot_type={state.plot_type.value}, filtered_rows={len(df_f)}")
        figure_dict = self.figure_generator.make_figure(
            df_f, state, selected_row_ids=selected_row_ids or self._selected_row_ids or None
        )
        logger.debug(f"Figure generated: {len(figure_dict.get('data', []))} traces")
        return figure_dict


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