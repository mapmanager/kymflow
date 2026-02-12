# app.py
from __future__ import annotations

from typing import Any, Optional

from pprint import pprint
import pandas as pd
from nicegui import ui
from nicegui.events import GenericEventArguments

from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.gui_v2.app_context import _setUpGuiDefaults
from kymflow.core.plotting.pool.plot_state import PlotType, PlotState
from kymflow.core.plotting.pool.plot_helpers import numeric_columns, is_categorical_column
from kymflow.core.plotting.pool.dataframe_processor import DataFrameProcessor
from kymflow.core.plotting.pool.figure_generator import FigureGenerator
from kymflow.core.plotting.pool.pool_control_panel import PoolControlPanel
from kymflow.core.plotting.pool.selection_handler import PlotSelectionHandler, is_selection_compatible

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
        plot_state: Optional[PlotState] = None,
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
        if plot_state is None:
            default_state = PlotState(
                roi_id=roi_values[0],
                xcol=x_default,
                ycol=y_default,
            )
        else:
            default_state = plot_state
        
        # Store default plot state for reset functionality
        self.default_plot_state: PlotState = PlotState.from_dict(default_state.to_dict())
        
        # Try to load saved config, otherwise use provided/default plot_state
        from kymflow.core.plotting.pool.pool_plot_config import PoolPlotConfig
        config = PoolPlotConfig.load()
        loaded_plot_states = config.get_plot_states()
        loaded_layout = config.get_layout()
        
        if loaded_plot_states:
            logger.info(f"Loaded {len(loaded_plot_states)} plot state(s) and layout '{loaded_layout}' from pool_plot_config.json")
            # Use loaded layout
            self.layout = loaded_layout
            # Use loaded plot states, pad with default_state if needed
            num_plots_needed = self._get_num_plots_for_layout(loaded_layout)
            self.plot_states = []
            for i in range(num_plots_needed):
                if i < len(loaded_plot_states):
                    self.plot_states.append(loaded_plot_states[i])
                else:
                    self.plot_states.append(PlotState.from_dict(default_state.to_dict()))
            # Update stored default to match first loaded state
            self.default_plot_state = PlotState.from_dict(self.plot_states[0].to_dict())
        else:
            logger.info("No saved plot config found, using provided/default plot state")
            self.layout = "1x1"
            # Initialize with 4 plot states to support 2x2 layout
            self.plot_states = [
                PlotState.from_dict(default_state.to_dict()),
                PlotState.from_dict(default_state.to_dict()),
                PlotState.from_dict(default_state.to_dict()),
                PlotState.from_dict(default_state.to_dict()),
            ]
        
        self.current_plot_index: int = 0

        # UI handles
        self._plots: list[ui.plotly] = []
        self._clicked_label: Optional[ui.label] = None
        self._mainSplitter: Optional[ui.splitter] = None
        self._last_plot_type: Optional[PlotType] = None
        self._plot_container: Optional[ui.column] = None
        self._selection_label: Optional[ui.label] = None
        self._control_panel: Optional[PoolControlPanel] = None

        # row_id -> iloc index within CURRENT filtered df (rebuilt each replot)
        self._id_to_index_filtered: dict[str, int] = {}

        # Linked selection (owned by handler; controller uses get_selected_row_ids())
        self._selection_handler = PlotSelectionHandler(
            data_processor=self.data_processor,
            figure_generator=self.figure_generator,
            row_id_col=self.row_id_col,
            get_filtered_df=self._get_filtered_df,
            on_apply_selection=self._apply_selection_to_all_plots,
            on_update_label=self._set_selection_label_count,
        )

    def _get_filtered_df(self, state: PlotState) -> pd.DataFrame:
        """Return dataframe filtered by state.roi_id for selection/plot use."""
        if state.roi_id and state.roi_id != 0:
            return self.data_processor.filter_by_roi(state.roi_id)
        return self.data_processor.df.dropna(subset=[self.data_processor.row_id_col])

    def _set_selection_label_count(self, count: int) -> None:
        """Update selection label text (callback from selection handler)."""
        if self._selection_label is not None:
            self._selection_label.text = f"{count} points selected" if count else "No selection"

    def _state_to_widgets(self, state: PlotState) -> None:
        """Populate all UI widgets from a PlotState."""
        if self._control_panel is None:
            return
        self._control_panel.bind_state(state)
        self._control_panel.sync_controls(state.plot_type, state.show_std_sem)

    def _widgets_to_state(self) -> PlotState:
        """Create PlotState from current UI widget values. xcol/ycol from current plot state (aggrid async)."""
        if self._control_panel is None:
            return self.plot_states[self.current_plot_index]
        current = self.plot_states[self.current_plot_index]
        return self._control_panel.get_state(xcol=current.xcol, ycol=current.ycol)



    # ----------------------------
    # UI
    # ----------------------------

    def build(self) -> None:
        """Build the main UI layout with header, splitter, controls, and plot."""
        # Header area at the top
        with ui.column().classes("w-full"):
            with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                ui.label("Radon Analysis Pool Plot").classes("text-2xl font-bold mb-2")
                ui.button("Open CSV", on_click=self._on_open_csv).classes("text-sm")
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
            value=30,  # Increased from 25 to give more horizontal room to toolbar
            limits=(15, 50),
            on_change=lambda _: self._on_splitter_change(),
        ).classes("w-full h-screen")
        
        # LEFT: Control panel
        roi_options = ["(none)"] + [str(r) for r in self.data_processor.get_roi_values()]
        self._control_panel = PoolControlPanel(
            self.df,
            layout=self.layout,
            current_plot_index=self.current_plot_index,
            initial_state=self.plot_states[self.current_plot_index],
            on_any_change=self._on_any_change,
            on_layout_change=self._on_layout_change,
            on_save_config=self._save_config,
            on_plot_radio_change=self._on_plot_radio_change,
            on_apply_current_to_others=self._apply_current_to_others,
            on_replot_current=self._replot_current,
            on_reset_to_default=self._reset_to_default,
            on_x_column_selected=self._on_x_column_selected,
            on_y_column_selected=self._on_y_column_selected,
        )
        with self._mainSplitter.before:
            self._control_panel.build(roi_options=roi_options)

        # RIGHT: Plot panel
        with self._mainSplitter.after:
            self._plot_container = ui.column().classes("w-full h-full")
        self._rebuild_plot_panel()

        self._control_panel.sync_controls(
            self.plot_states[self.current_plot_index].plot_type,
            self.plot_states[self.current_plot_index].show_std_sem,
        )
        self._state_to_widgets(self.plot_states[self.current_plot_index])
        self._set_selection_label_count(len(self._selection_handler.get_selected_row_ids()))

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
                    if is_selection_compatible(self.plot_states[0].plot_type):
                        plot.on("plotly_relayout", lambda e, idx=0: self._on_plotly_relayout(e, plot_index=idx))
                    self._plots.append(plot)
        
        elif rows == 1 and cols == 2:
            # 1x2: Two plots side by side
            with self._plot_container:
                with ui.row().classes("w-full h-full gap-2 no-wrap"):
                    for i in range(2):
                        with ui.column().classes("flex-1 w-0 h-full min-h-0 p-4"):
                            plot = ui.plotly(
                                self._make_figure_dict(self.plot_states[i], selected_row_ids=None)
                            ).classes("w-full h-full")
                            plot.on("plotly_click", lambda e, idx=i: self._on_plotly_click(e, plot_index=idx))
                            if is_selection_compatible(self.plot_states[i].plot_type):
                                plot.on("plotly_relayout", lambda e, idx=i: self._on_plotly_relayout(e, plot_index=idx))
                            self._plots.append(plot)
        
        elif rows == 2 and cols == 1:
            # 2x1: Two plots stacked vertically
            with self._plot_container:
                with ui.column().classes("w-full h-full gap-2"):
                    for i in range(2):
                        with ui.column().classes("w-full flex-1 min-h-0 p-4"):
                            plot = ui.plotly(
                                self._make_figure_dict(self.plot_states[i], selected_row_ids=None)
                            ).classes("w-full h-full")
                            plot.on("plotly_click", lambda e, idx=i: self._on_plotly_click(e, plot_index=idx))
                            if is_selection_compatible(self.plot_states[i].plot_type):
                                plot.on("plotly_relayout", lambda e, idx=i: self._on_plotly_relayout(e, plot_index=idx))
                            self._plots.append(plot)
        
        elif rows == 2 and cols == 2:
            # 2x2: Four plots in a 2x2 grid
            with self._plot_container:
                with ui.column().classes("w-full h-full gap-2"):
                    for row_idx in range(2):
                        with ui.row().classes("w-full flex-1 gap-2 min-h-0 no-wrap"):
                            for col_idx in range(2):
                                plot_idx = row_idx * 2 + col_idx
                                with ui.column().classes("flex-1 w-0 h-full min-h-0 p-4"):
                                    plot = ui.plotly(
                                        self._make_figure_dict(self.plot_states[plot_idx], selected_row_ids=None)
                                    ).classes("w-full h-full")
                                    plot.on("plotly_click", lambda e, idx=plot_idx: self._on_plotly_click(e, plot_index=idx))
                                    if is_selection_compatible(self.plot_states[plot_idx].plot_type):
                                        plot.on("plotly_relayout", lambda e, idx=plot_idx: self._on_plotly_relayout(e, plot_index=idx))
                                    self._plots.append(plot)
        
        # Initialize last plot type tracking after plots are created
        if self._plots and self._last_plot_type is None:
            self._last_plot_type = self.plot_states[self.current_plot_index].plot_type

    # ----------------------------
    # Events
    # ----------------------------

    def _on_splitter_change(self) -> None:
        """Restore plot panel after splitter resize (avoids 1x2/2x1 collapsing to single plot)."""
        self._rebuild_plot_panel()

    def _get_num_plots_for_layout(self, layout_str: str) -> int:
        """Get number of plots needed for a layout string.
        
        Args:
            layout_str: Layout string like "1x1", "1x2", "2x1", "2x2".
            
        Returns:
            Number of plots needed.
        """
        rows, cols = map(int, layout_str.split('x'))
        return rows * cols
    
    def _on_plot_radio_change(self, e) -> None:
        """Handle plot radio button change with validation.
        
        Validates that the selected plot index is valid for the current layout.
        If invalid, reverts to a valid selection.
        """
        try:
            selected_plot_num = int(e.value)
            plot_index = selected_plot_num - 1
            
            # Validate that this plot index is available for current layout
            num_plots = self._get_num_plots_for_layout(self.layout)
            if plot_index < 0 or plot_index >= num_plots:
                logger.warning(f"Invalid plot selection {selected_plot_num} for layout {self.layout} (max {num_plots} plots)")
                if self._control_panel and self._control_panel._plot_radio:
                    self._control_panel._plot_radio.value = str(self.current_plot_index + 1)
                ui.notify(f"Plot {selected_plot_num} is not available for layout {self.layout}", type="warning")
                return
            self._on_plot_selection_change(plot_index)
        except (ValueError, TypeError) as ex:
            logger.error(f"Error parsing plot radio selection: {ex}")
            if self._control_panel and self._control_panel._plot_radio:
                self._control_panel._plot_radio.value = str(self.current_plot_index + 1)
    
    def _on_layout_change(self, layout_str: str) -> None:
        """Handle layout change (1x1, 1x2, 2x1, 2x2).
        
        Args:
            layout_str: Layout string like "1x1", "1x2", "2x1", "2x2".
        """
        logger.info(f"Layout changed to: {layout_str}")
        # Save current plot state before changing layout
        self.plot_states[self.current_plot_index] = self._widgets_to_state()
        
        # Ensure we have enough plot states for the new layout
        num_plots_needed = self._get_num_plots_for_layout(layout_str)
        current_state = self.plot_states[self.current_plot_index]
        
        # Pad plot_states if needed
        while len(self.plot_states) < num_plots_needed:
            self.plot_states.append(PlotState.from_dict(current_state.to_dict()))
        
        # Clamp current_plot_index if needed
        if self.current_plot_index >= num_plots_needed:
            self.current_plot_index = num_plots_needed - 1
        
        self.layout = layout_str
        
        # Ensure current selection is valid
        num_plots = self._get_num_plots_for_layout(layout_str)
        if self.current_plot_index >= num_plots:
            self.current_plot_index = num_plots - 1
        
        if self._control_panel and self._control_panel._plot_radio:
            self._control_panel._plot_radio.value = str(self.current_plot_index + 1)
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

    def _save_config(self) -> None:
        """Save current layout and all plot states to config file."""
        from kymflow.core.plotting.pool.pool_plot_config import PoolPlotConfig
        
        # Save current plot state before saving
        self.plot_states[self.current_plot_index] = self._widgets_to_state()
        
        # Load existing config and update layout and plot_states
        config = PoolPlotConfig.load()
        config.set_layout(self.layout)
        config.set_plot_states(self.plot_states)
        config.save()
        
        ui.notify(f"Plot configuration saved (layout: {self.layout}, {len(self.plot_states)} plot(s))", type="positive")

    def _reset_to_default(self) -> None:
        """Reset all plots to the default plot state."""
        logger.info("Resetting all plots to default state")
        # Apply default state to all plots
        for i in range(len(self.plot_states)):
            self.plot_states[i] = PlotState.from_dict(self.default_plot_state.to_dict())
        
        # Update widgets to reflect default state
        self._state_to_widgets(self.plot_states[self.current_plot_index])
        
        # Replot all visible plots
        self._replot_all()
        ui.notify("Plots reset to default configuration", type="info")

    def _on_x_column_selected(self, row_dict: dict[str, Any]) -> None:
        """Callback when X column is selected in aggrid."""
        column_name = row_dict.get("column")
        if not column_name:
            logger.warning(f"X column selection callback received invalid row_dict: {row_dict}")
            return
        column_name = str(column_name)
        # Box/Violin/Swarm don't use xcol for x-axis (they use group_col), so no validation needed here
        # X column selection is still allowed but won't affect these plot types
        logger.info(f"X column selected: {column_name}")
        self.plot_states[self.current_plot_index].xcol = column_name
        self._on_any_change()

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
        if self._control_panel is None:
            return
        logger.info("Control change detected, updating state and replotting")
        new_state = self._widgets_to_state()
        new_state.xcol = self.plot_states[self.current_plot_index].xcol
        new_state.ycol = self.plot_states[self.current_plot_index].ycol

        if new_state.plot_type in (PlotType.BOX_PLOT, PlotType.VIOLIN, PlotType.SWARM):
            if not new_state.group_col or new_state.group_col == "(none)":
                ui.notify(
                    "Box/Violin/Swarm plots require a Group/Color column for x-axis. Select a categorical column.",
                    type="warning",
                )
                new_state.group_col = self.plot_states[self.current_plot_index].group_col
                self._control_panel._group_select.value = new_state.group_col if new_state.group_col else "(none)"
            elif not is_categorical_column(self.df, new_state.group_col):
                ui.notify(
                    "Group/Color column must be categorical for Box/Violin/Swarm plots.",
                    type="warning",
                )
                new_state.group_col = self.plot_states[self.current_plot_index].group_col
                self._control_panel._group_select.value = new_state.group_col if new_state.group_col else "(none)"
            if new_state.color_grouping and not is_categorical_column(self.df, new_state.color_grouping):
                ui.notify("Group/Nesting column must be categorical.", type="warning")
                new_state.color_grouping = self.plot_states[self.current_plot_index].color_grouping
                self._control_panel._color_grouping_select.value = new_state.color_grouping if new_state.color_grouping else "(none)"

        self.plot_states[self.current_plot_index] = new_state
        self._control_panel.sync_controls(new_state.plot_type, new_state.show_std_sem)
        self._replot_current()

    def _clear_selection(self) -> None:
        """Clear linked selection and refresh all compatible plots."""
        self._selection_handler.handle_clear()

    def _on_open_csv(self) -> None:
        """Open a CSV file via native dialog. Replace with pywebview callback when available."""
        # Dummy for now: wire pywebview native file-open callback here
        ui.notify("Open CSV: connect pywebview file dialog callback here", type="info")

    def _on_keyboard_key(self, e) -> None:
        key_name = getattr(getattr(e, "key", None), "name", None) if e else None
        action = getattr(e, "action", None)
        self._selection_handler.handle_key(key_name, action)

    def _on_plotly_relayout(self, e: GenericEventArguments, plot_index: int = 0) -> None:
        raw = e.args
        if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], dict):
            payload = raw[0]
        elif isinstance(raw, dict):
            payload = raw
        else:
            payload = {}
        state = self.plot_states[plot_index]
        self._selection_handler.handle_relayout(payload, plot_index, state)

    def select_points_by_row_id(self, row_id: str) -> None:
        """Programmatically select points by row_id (delegates to selection handler)."""
        self._selection_handler.select_by_row_id(row_id, self.plot_states)

    def _apply_selection_to_all_plots(self) -> None:
        """Update all selection-compatible plots to show the current linked selection."""
        selected = self._selection_handler.get_selected_row_ids()
        for i in range(len(self._plots)):
            if i >= len(self.plot_states):
                break
            if not is_selection_compatible(self.plot_states[i].plot_type):
                continue
            fig_dict = self._make_figure_dict(self.plot_states[i], selected_row_ids=selected)
            self._plots[i].update_figure(fig_dict)
            self._plots[i].update()

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
        if state.plot_type in {PlotType.SCATTER, PlotType.SWARM}:
            row_id: Optional[str] = None
            if isinstance(custom, (str, int, float)):
                row_id = str(custom)
            elif isinstance(custom, (list, tuple)) and custom:
                row_id = str(custom[0])

            if not row_id:
                logger.debug(f"Could not extract row_id from plotly click: custom={custom}")
                return

            logger.info(f"Plotly click on plot {plot_index + 1}: plot_type={state.plot_type.value}, row_id={row_id}")

            # Filter by ROI if roi_id is set (not 0/None from "(none)" selection)
            if state.roi_id and state.roi_id != 0:
                df_f = self.data_processor.filter_by_roi(state.roi_id)
            else:
                df_f = self.data_processor.df.dropna(subset=[self.data_processor.row_id_col])
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
        
        selected = self._selection_handler.get_selected_row_ids()
        for i in range(min(num_plots, len(self._plots), len(self.plot_states))):
            state = self.plot_states[i]
            self._plots[i].update_figure(
                self._make_figure_dict(state, selected_row_ids=selected or None)
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
        # Filter by ROI if roi_id is set (not 0/None from "(none)" selection)
        if state.roi_id and state.roi_id != 0:
            df_f = self.data_processor.filter_by_roi(state.roi_id)
        else:
            df_f = self.data_processor.df.dropna(subset=[self.data_processor.row_id_col])
        self._id_to_index_filtered = self.data_processor.build_row_id_index(df_f)
        
        logger.debug(f"Making figure: plot_type={state.plot_type.value}, filtered_rows={len(df_f)}")
        figure_dict = self.figure_generator.make_figure(
            df_f, state, selected_row_ids=selected_row_ids or self._selection_handler.get_selected_row_ids() or None
        )
        logger.debug(f"Figure generated: {len(figure_dict.get('data', []))} traces")
        return figure_dict


# ----------------------------
# Demo entrypoint
# ----------------------------

def main() -> None:
    """Demo entrypoint: load data and launch the plot controller UI."""

    path = '/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v2-analysis/radon_report.csv'

    df = pd.read_csv(path)

    # print(df.head())

    _setUpGuiDefaults()
    
    ui.page_title("NiceGUI + Plotly (ROI filter + click row)")
    # ui.label("Filter by ROI, replot, and click points to print the filtered df row.").classes("text-lg font-medium")

    # Create default plot state
    default_plot_state = PlotState(
        roi_id=0,  # (none) - show all ROIs
        xcol="img_mean",
        ycol="vel_mean",
        plot_type=PlotType.SCATTER,
        group_col="grandparent_folder",
        color_grouping="roi_id",
        use_absolute_value=True,
        use_remove_values=True,
        remove_values_threshold=10000.0,
    )

    default_plot_state = None
    ctrl = PlotController(df, roi_id_col="roi_id", row_id_col="path", plot_state=default_plot_state)
    ctrl.build()
    
    # Example: programmatically select a point by row_id
    # TODO: Replace with actual row_id value from your data
    # _select_path = '/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v1-analysis/14d Saline/20251014/20251014_A98_0002.tif'
    # ctrl.select_points_by_row_id(_select_path)

    native_bool = True
    reload_bool = True
    ui.run(reload=reload_bool,
            native=native_bool,
            window_size=(1400, 800)
            )


if __name__ in {"__main__", "__mp_main__"}:
    main()