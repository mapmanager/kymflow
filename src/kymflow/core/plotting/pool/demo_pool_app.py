# app.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from pprint import pprint
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from nicegui import ui
from nicegui.events import GenericEventArguments

from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.gui_v2.app_context import _setUpGuiDefaults

logger = get_logger(__name__)
setup_logging(level="INFO")

# CSS for compact aggrid styling (injected once)
_AGGRID_COMPACT_CSS_INJECTED = False


def _ensure_aggrid_compact_css() -> None:
    """Inject CSS for compact aggrid styling (smaller font, tighter spacing)."""
    global _AGGRID_COMPACT_CSS_INJECTED
    if not _AGGRID_COMPACT_CSS_INJECTED:
        ui.add_head_html("""
        <style>
        .aggrid-compact .ag-cell,
        .aggrid-compact .ag-header-cell {
            padding: 2px 6px;
            font-size: 0.75rem;
            line-height: 1.2;
        }
        </style>
        """)
        _AGGRID_COMPACT_CSS_INJECTED = True

# ----------------------------
# State
# ----------------------------

class PlotType(Enum):
    """Enumeration of available plot types."""
    SCATTER = "scatter"
    SPLIT_SCATTER = "split_scatter"
    SWARM = "swarm"
    GROUPED = "grouped"
    CUMULATIVE_HISTOGRAM = "cumulative_histogram"


@dataclass
class PlotState:
    roi_id: int
    xcol: str
    ycol: str
    plot_type: PlotType = PlotType.SCATTER
    group_col: Optional[str] = None    # used by grouped/split_scatter/swarm
    ystat: str = "mean"                # used by grouped only
    use_absolute_value: bool = False   # apply abs() to y values before plotting
    show_mean: bool = False            # show mean line for split_scatter/swarm
    show_std_sem: bool = False         # show std/sem error bars for split_scatter/swarm
    std_sem_type: str = "std"          # "std" or "sem" for error bars
    mean_line_width: int = 2           # line width for mean line
    error_line_width: int = 2          # line width for error (std/sem) line
    show_raw: bool = True              # show raw data points
    point_size: int = 6                # size of scatter/swarm plot points
    show_legend: bool = True           # show plot legend


# ----------------------------
# Helpers
# ----------------------------

_NUMERIC_KINDS = {"i", "u", "f"}  # int, unsigned, float (pandas dtype.kind)


def numeric_columns(df: pd.DataFrame) -> list[str]:
    """Extract list of numeric column names from dataframe."""
    out: list[str] = []
    for c in df.columns:
        s = df[c]
        if getattr(s.dtype, "kind", None) in _NUMERIC_KINDS:
            out.append(str(c))
    return out


def categorical_candidates(df: pd.DataFrame) -> list[str]:
    """Heuristic: object/category/bool, or low-ish cardinality."""
    out: list[str] = []
    n = len(df)
    for c in df.columns:
        s = df[c]
        kind = getattr(s.dtype, "kind", None)
        if kind in {"O", "b"} or str(s.dtype) == "category":
            out.append(str(c))
            continue
        nunique = s.nunique(dropna=True)
        if n > 0 and nunique <= max(20, int(0.05 * n)):
            out.append(str(c))
    return out


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

        if self.roi_id_col not in df.columns:
            raise ValueError(f"df must contain required column {roi_id_col!r}")
        if self.row_id_col not in df.columns:
            raise ValueError(f"df must contain required unique id column {row_id_col!r}")

        roi_values = self._roi_values()
        if not roi_values:
            raise ValueError(f"No ROI values found in column {roi_id_col!r}")

        # reasonable defaults
        num_cols = numeric_columns(df)
        if not num_cols:
            raise ValueError("Need at least one numeric column for y.")
        x_default = num_cols[0]
        y_default = num_cols[1] if len(num_cols) >= 2 else num_cols[0]

        self.state = PlotState(
            roi_id=roi_values[0],
            xcol=x_default,
            ycol=y_default,
        )

        # UI handles
        self._plot: Optional[ui.plotly] = None
        self._clicked_label: Optional[ui.label] = None
        self._mainSplitter: Optional[ui.splitter] = None

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

    def _roi_values(self) -> list[int]:
        """Get sorted list of unique ROI IDs from the dataframe."""
        s = pd.to_numeric(self.df[self.roi_id_col], errors="coerce").dropna().astype(int)
        vals = sorted(set(s.tolist()))
        return vals

    def _df_filtered(self) -> pd.DataFrame:
        """Filter dataframe to rows matching the current ROI ID."""
        df_f = self.df[self.df[self.roi_id_col].astype(int) == int(self.state.roi_id)]
        df_f = df_f.dropna(subset=[self.row_id_col])
        return df_f

    def _rebuild_filtered_index(self, df_f: pd.DataFrame) -> None:
        """Rebuild the mapping from row_id to iloc index in the filtered dataframe."""
        row_ids = df_f[self.row_id_col].astype(str).tolist()
        # map row_id -> iloc within df_f
        self._id_to_index_filtered = {rid: i for i, rid in enumerate(row_ids)}

    def _get_y_values(self, df_f: pd.DataFrame) -> pd.Series:
        """Get y column values, optionally applying absolute value.
        
        Args:
            df_f: Filtered dataframe.
            
        Returns:
            Series of y values, with abs() applied if use_absolute_value is True.
        """
        y = pd.to_numeric(df_f[self.state.ycol], errors="coerce")
        if self.state.use_absolute_value:
            y = y.abs()
        return y

    def _calculate_group_stats(self, df_f: pd.DataFrame, include_x: bool = False) -> dict[str, dict[str, float]]:
        """Calculate mean, std, and sem for y values (and optionally x values) within each group.
        
        Args:
            df_f: Filtered dataframe with group column and y values.
            include_x: If True, also calculate stats for x values (for split_scatter).
            
        Returns:
            Dictionary mapping group_value to stats dict with keys: "mean", "std", "sem"
            (and "x_mean", "x_std", "x_sem" if include_x=True).
        """
        if not self.state.group_col:
            return {}
        
        y = self._get_y_values(df_f)
        g = df_f[self.state.group_col].astype(str)
        
        if include_x:
            x = pd.to_numeric(df_f[self.state.xcol], errors="coerce")
            tmp = pd.DataFrame({"x": x, "y": y, "g": g}).dropna(subset=["y", "g", "x"])
        else:
            tmp = pd.DataFrame({"y": y, "g": g}).dropna(subset=["y", "g"])
        
        stats = {}
        for group_value, sub in tmp.groupby("g", sort=True):
            y_values = sub["y"].values
            if len(y_values) > 0:
                mean_val = float(np.mean(y_values))
                std_val = float(np.std(y_values, ddof=1))  # Sample std
                sem_val = std_val / np.sqrt(len(y_values)) if len(y_values) > 1 else 0.0
                
                group_stats = {
                    "mean": mean_val,
                    "std": std_val,
                    "sem": sem_val,
                }
                
                # Add x-axis stats if requested
                if include_x:
                    x_values = sub["x"].values
                    if len(x_values) > 0:
                        x_mean_val = float(np.mean(x_values))
                        x_std_val = float(np.std(x_values, ddof=1))
                        x_sem_val = x_std_val / np.sqrt(len(x_values)) if len(x_values) > 1 else 0.0
                        group_stats.update({
                            "x_mean": x_mean_val,
                            "x_std": x_std_val,
                            "x_sem": x_sem_val,
                        })
                
                stats[str(group_value)] = group_stats
        
        return stats

    def _add_mean_std_traces(
        self, 
        fig: go.Figure, 
        group_stats: dict[str, dict[str, float]], 
        x_ranges: dict[str, tuple[float, float]],
        include_x_axis: bool = False,
    ) -> None:
        """Add mean and std/sem traces to figure.
        
        Args:
            fig: Plotly figure to add traces to.
            group_stats: Dictionary from _calculate_group_stats().
            x_ranges: Dictionary mapping group_value to (x_min, x_max) tuple.
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
            if self.state.show_mean:
                fig.add_trace(go.Scatter(
                    x=[x_min, x_max],
                    y=[mean_val, mean_val],
                    mode="lines",
                    name=f"{group_value} (y-mean)",
                    line=dict(color="gray", width=self.state.mean_line_width),
                    showlegend=False,  # Hide mean/std/sem traces from legend
                    hovertemplate=f"Y Mean: {mean_val:.3f}<extra></extra>",
                ))
            
            # Add vertical line for y-std/sem (hide from legend)
            if self.state.show_std_sem:
                error_val = stats[self.state.std_sem_type]
                y_min = mean_val - error_val
                y_max = mean_val + error_val
                x_center = (x_min + x_max) / 2
                
                fig.add_trace(go.Scatter(
                    x=[x_center, x_center],
                    y=[y_min, y_max],
                    mode="lines",
                    name=f"{group_value} (y-{self.state.std_sem_type})",
                    line=dict(color="red", width=self.state.error_line_width),
                    showlegend=False,  # Hide mean/std/sem traces from legend
                    hovertemplate=(
                        f"Y Mean: {mean_val:.3f}<br>"
                        f"Y {self.state.std_sem_type.upper()}: ±{error_val:.3f}<br>"
                        f"Y Range: [{y_min:.3f}, {y_max:.3f}]<extra></extra>"
                    ),
                ))
            
            # Add x-axis mean and std/sem for split_scatter (hide from legend)
            if include_x_axis and "x_mean" in stats:
                x_mean_val = stats["x_mean"]
                x_error_val = stats[f"x_{self.state.std_sem_type}"]
                
                # Calculate y range for x-mean vertical line
                # Use y-std/sem range if available, otherwise use a range around y-mean
                if self.state.show_std_sem:
                    y_line_min = y_min
                    y_line_max = y_max
                else:
                    # Use a reasonable range around y-mean (10% of mean or fixed range)
                    y_range = abs(mean_val) * 0.1 if mean_val != 0 else 1.0
                    y_line_min = mean_val - y_range
                    y_line_max = mean_val + y_range
                
                # Add vertical line for x-mean
                if self.state.show_mean:
                    fig.add_trace(go.Scatter(
                        x=[x_mean_val, x_mean_val],
                        y=[y_line_min, y_line_max],
                        mode="lines",
                        name=f"{group_value} (x-mean)",
                        line=dict(color="blue", width=self.state.mean_line_width),
                        showlegend=False,  # Hide mean/std/sem traces from legend
                        hovertemplate=f"X Mean: {x_mean_val:.3f}<extra></extra>",
                    ))
                
                # Add horizontal line for x-std/sem
                if self.state.show_std_sem:
                    x_min_error = x_mean_val - x_error_val
                    x_max_error = x_mean_val + x_error_val
                    y_center = mean_val
                    
                    fig.add_trace(go.Scatter(
                        x=[x_min_error, x_max_error],
                        y=[y_center, y_center],
                        mode="lines",
                        name=f"{group_value} (x-{self.state.std_sem_type})",
                        line=dict(color="orange", width=self.state.error_line_width),
                        showlegend=False,  # Hide mean/std/sem traces from legend
                        hovertemplate=(
                            f"X Mean: {x_mean_val:.3f}<br>"
                            f"X {self.state.std_sem_type.upper()}: ±{x_error_val:.3f}<br>"
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
        with self._mainSplitter.after:
            self._build_plot_panel()

        self._sync_controls()
        self.replot()

    def _build_control_panel(self) -> None:
        """Build the left control panel with all plot configuration widgets.
        
        Creates a modular control panel that can be inserted into any container.
        All widgets are stored as instance attributes for later access.
        """
        with ui.column().classes("w-full h-full p-4 gap-4 overflow-y-auto"):
            self._roi_select = ui.select(
                options=self._roi_values(),
                value=self.state.roi_id,
                label="ROI",
                on_change=self._on_any_change,
            ).classes("w-full")

            self._type_select = ui.select(
                options={pt.value: pt.value for pt in PlotType},
                value=self.state.plot_type.value,
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
                value=self.state.ystat,
                label="Y stat (grouped)",
                on_change=self._on_any_change,
            ).classes("w-full")

            self._abs_value_checkbox = ui.checkbox(
                "Absolute Value",
                value=self.state.use_absolute_value,
                on_change=self._on_any_change,
            ).classes("w-full")

            # Mean/Std/Sem controls (only for split_scatter and swarm)
            ui.label("Mean/Std/Sem (split_scatter & swarm only)").classes("text-sm font-semibold mt-2")
            with ui.row().classes("w-full gap-2 items-center"):
                self._show_mean_checkbox = ui.checkbox(
                    "Mean",
                    value=self.state.show_mean,
                    on_change=self._on_any_change,
                )
                
                self._show_std_sem_checkbox = ui.checkbox(
                    "+/-",
                    value=self.state.show_std_sem,
                    on_change=self._on_any_change,
                )
                
                self._std_sem_select = ui.select(
                    options=["std", "sem"],
                    value=self.state.std_sem_type,
                    label="",
                    on_change=self._on_any_change,
                ).classes("flex-1")

            # X and Y column selection using aggrid
            ui.label("Column Selection").classes("text-sm font-semibold mt-2")
            with ui.row().classes("w-full gap-2 items-start"):
                # X column aggrid
                with ui.column().classes("flex-1"):
                    self._x_aggrid = self._create_column_aggrid("X column", self.state.xcol, self._on_x_column_selected)
                
                # Y column aggrid
                with ui.column().classes("flex-1"):
                    self._y_aggrid = self._create_column_aggrid("Y column", self.state.ycol, self._on_y_column_selected)

            ui.button("Replot", on_click=self.replot).classes("w-full")

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
                        value=self.state.mean_line_width,
                        min=1,
                        max=10,
                        step=1,
                        on_change=self._on_any_change,
                    ).classes("flex-1")
                    
                    self._error_line_width_input = ui.number(
                        label="Error Line Width",
                        value=self.state.error_line_width,
                        min=1,
                        max=10,
                        step=1,
                        on_change=self._on_any_change,
                    ).classes("flex-1")
                
                # Raw data and Point size in same row
                with ui.row().classes("w-full gap-2 items-center"):
                    self._show_raw_checkbox = ui.checkbox(
                        "Raw",
                        value=self.state.show_raw,
                        on_change=self._on_any_change,
                    )
                    
                    self._point_size_input = ui.number(
                        label="Point Size",
                        value=self.state.point_size,
                        min=1,
                        max=20,
                        step=1,
                        on_change=self._on_any_change,
                    ).classes("flex-1")
                
                # Legend
                self._show_legend_checkbox = ui.checkbox(
                    "Legend",
                    value=self.state.show_legend,
                    on_change=self._on_any_change,
                ).classes("w-full")

    def _build_plot_panel(self) -> None:
        """Build the right plot panel with the Plotly visualization.
        
        Creates a modular plot panel that can be inserted into any container.
        The plot widget is stored as instance attribute for later updates.
        """
        with ui.column().classes("w-full h-full min-h-0 p-4"):
            self._plot = ui.plotly(self._make_figure_dict()).classes("w-full h-full")
            self._plot.on("plotly_click", self._on_plotly_click)

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

    def _on_x_column_selected(self, row_dict: dict[str, Any]) -> None:
        """Callback when X column is selected in aggrid."""
        column_name = row_dict.get("column")
        if column_name:
            logger.info(f"X column selected: {column_name}")
            self.state.xcol = str(column_name)
            self._on_any_change()
        else:
            logger.warning(f"X column selection callback received invalid row_dict: {row_dict}")

    def _on_y_column_selected(self, row_dict: dict[str, Any]) -> None:
        """Callback when Y column is selected in aggrid."""
        column_name = row_dict.get("column")
        if column_name:
            logger.info(f"Y column selected: {column_name}")
            self.state.ycol = str(column_name)
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
        
        self.state.roi_id = int(self._roi_select.value)
        # Convert string value to PlotType enum
        plot_type_str = str(self._type_select.value)
        try:
            self.state.plot_type = PlotType(plot_type_str)
        except ValueError:
            logger.warning(f"Invalid plot type '{plot_type_str}', defaulting to SCATTER")
            self.state.plot_type = PlotType.SCATTER
        self.state.ystat = str(self._ystat_select.value)

        gv = str(self._group_select.value)
        self.state.group_col = None if gv == "(none)" else gv

        self.state.use_absolute_value = bool(self._abs_value_checkbox.value)
        if self.state.use_absolute_value:
            logger.info("Absolute value enabled: y values will be converted to |y| before plotting")

        self.state.show_mean = bool(self._show_mean_checkbox.value)
        self.state.show_std_sem = bool(self._show_std_sem_checkbox.value)
        self.state.std_sem_type = str(self._std_sem_select.value)

        # Plot options
        self.state.mean_line_width = int(self._mean_line_width_input.value) if self._mean_line_width_input.value is not None else 2
        self.state.error_line_width = int(self._error_line_width_input.value) if self._error_line_width_input.value is not None else 2
        self.state.show_raw = bool(self._show_raw_checkbox.value)
        self.state.point_size = int(self._point_size_input.value) if self._point_size_input.value is not None else 6
        self.state.show_legend = bool(self._show_legend_checkbox.value)

        logger.debug(
            f"State updated: roi_id={self.state.roi_id}, plot_type={self.state.plot_type.value}, "
            f"xcol={self.state.xcol}, ycol={self.state.ycol}, group_col={self.state.group_col}, "
            f"use_absolute_value={self.state.use_absolute_value}, "
            f"show_mean={self.state.show_mean}, show_std_sem={self.state.show_std_sem}, "
            f"std_sem_type={self.state.std_sem_type}, "
            f"mean_line_width={self.state.mean_line_width}, error_line_width={self.state.error_line_width}, "
            f"show_raw={self.state.show_raw}, point_size={self.state.point_size}, show_legend={self.state.show_legend}"
        )

        self._sync_controls()
        self.replot()

    def _sync_controls(self) -> None:
        """Enable/disable controls based on current plot type."""
        assert self._group_select and self._ystat_select
        assert self._show_mean_checkbox and self._show_std_sem_checkbox and self._std_sem_select
        
        needs_group = self.state.plot_type in {
            PlotType.GROUPED, 
            PlotType.SPLIT_SCATTER, 
            PlotType.SWARM,
            PlotType.CUMULATIVE_HISTOGRAM,
        }
        is_grouped_agg = self.state.plot_type == PlotType.GROUPED
        show_mean_std = self.state.plot_type in {PlotType.SPLIT_SCATTER, PlotType.SWARM}
        
        self._group_select.set_enabled(needs_group)
        self._ystat_select.set_enabled(is_grouped_agg)
        self._show_mean_checkbox.set_enabled(show_mean_std)
        self._show_std_sem_checkbox.set_enabled(show_mean_std)
        self._std_sem_select.set_enabled(show_mean_std and self.state.show_std_sem)
        
        logger.debug(
            f"Controls synced: group_select enabled={needs_group}, "
            f"ystat_select enabled={is_grouped_agg}, "
            f"mean/std controls enabled={show_mean_std}"
        )

    def _on_plotly_click(self, e: GenericEventArguments) -> None:
        """Handle click events on the Plotly plot."""
        points = (e.args or {}).get("points") or []
        if not points:
            logger.debug("Plotly click event received but no points found")
            return

        p0: dict[str, Any] = points[0]
        custom = p0.get("customdata")

        # per-row plots: click -> row_id -> filtered df row
        if self.state.plot_type in {PlotType.SCATTER, PlotType.SPLIT_SCATTER, PlotType.SWARM}:
            row_id: Optional[str] = None
            if isinstance(custom, (str, int, float)):
                row_id = str(custom)
            elif isinstance(custom, (list, tuple)) and custom:
                row_id = str(custom[0])

            if not row_id:
                logger.debug(f"Could not extract row_id from plotly click: custom={custom}")
                return

            logger.info(f"Plotly click: plot_type={self.state.plot_type.value}, row_id={row_id}")

            df_f = self._df_filtered()
            idx = self._id_to_index_filtered.get(row_id)
            if idx is None:
                logger.warning(f"Row ID {row_id} not found in filtered index")
                return

            row = df_f.iloc[idx]
            if self._clicked_label:
                self._clicked_label.text = f"ROI={self.state.roi_id} \n {self.row_id_col}={row_id} \n (filtered iloc={idx})"
            logger.info(f"Clicked row data: {row.to_dict()}")
            pprint(row.to_dict())
            return

        # grouped aggregation plot: click -> group summary
        if self.state.plot_type == PlotType.GROUPED:
            x = p0.get("x")
            y = p0.get("y")
            logger.info(f"Plotly click on grouped plot: group={x}, y={y}")
            if self._clicked_label:
                self._clicked_label.text = f"ROI={self.state.roi_id} clicked group={x}, y={y} (aggregated)"
            return

    # ----------------------------
    # Plotting
    # ----------------------------

    def replot(self) -> None:
        """Update the plot with current state and data."""
        assert self._plot is not None
        logger.debug("Replotting with current state")
        # Use update_figure() to properly refresh the plot
        # Setting .figure directly doesn't trigger a refresh
        self._plot.update_figure(self._make_figure_dict())

    def _make_figure_dict(self) -> dict:
        """Generate Plotly figure dictionary based on current plot type."""
        df_f = self._df_filtered()
        self._rebuild_filtered_index(df_f)

        logger.debug(f"Making figure: plot_type={self.state.plot_type.value}, filtered_rows={len(df_f)}")

        if self.state.plot_type == PlotType.GROUPED:
            return self._figure_grouped(df_f)
        if self.state.plot_type == PlotType.SPLIT_SCATTER:
            return self._figure_split_scatter(df_f)
        if self.state.plot_type == PlotType.SWARM:
            return self._figure_swarm(df_f)
        if self.state.plot_type == PlotType.CUMULATIVE_HISTOGRAM:
            return self._figure_cumulative_histogram(df_f)
        return self._figure_scatter(df_f)

    def _figure_scatter(self, df_f: pd.DataFrame) -> dict:
        """Create scatter plot figure."""
        x = df_f[self.state.xcol]
        y = self._get_y_values(df_f)
        row_ids = df_f[self.row_id_col].astype(str)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode="markers",
            name=f"ROI {self.state.roi_id}",
            customdata=row_ids,
            marker=dict(size=self.state.point_size),
            hovertemplate=(
                # f"roi_id={self.state.roi_id}<br>"
                f"{self.state.xcol}=%{{x}}<br>"
                f"{self.state.ycol}=%{{y}}<br>"
                # f"{self.row_id_col}=%{{customdata}}<extra></extra>"
            ),
        ))
        fig.update_layout(
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis_title=self.state.xcol,
            yaxis_title=self.state.ycol,
            showlegend=self.state.show_legend,
            uirevision="keep",
        )
        return fig.to_dict()

    def _figure_split_scatter(self, df_f: pd.DataFrame) -> dict:
        """Create split scatter plot with color coding by group column."""
        if not self.state.group_col:
            return self._figure_scatter(df_f)

        x = df_f[self.state.xcol]
        y = self._get_y_values(df_f)
        g = df_f[self.state.group_col].astype(str)
        row_ids = df_f[self.row_id_col].astype(str)

        tmp = pd.DataFrame({"x": x, "y": y, "g": g, "row_id": row_ids}).dropna(subset=["g"])
        fig = go.Figure()

        # Calculate y-axis range from raw data (for preserving range when show_raw is off)
        y_min_raw = float(tmp["y"].min()) if len(tmp) > 0 else None
        y_max_raw = float(tmp["y"].max()) if len(tmp) > 0 else None

        # Calculate x ranges for each group (for mean/std positioning)
        x_ranges = {}
        for group_value, sub in tmp.groupby("g", sort=True):
            x_ranges[str(group_value)] = (float(sub["x"].min()), float(sub["x"].max()))
            # Only add raw data trace if show_raw is True
            if self.state.show_raw:
                fig.add_trace(go.Scatter(
                    x=sub["x"],
                    y=sub["y"],
                    mode="markers",
                    name=str(group_value),
                    customdata=sub["row_id"],
                    marker=dict(size=self.state.point_size),
                    hovertemplate=(
                        # f"roi_id={self.state.roi_id}<br>"
                        f"{self.state.group_col}={group_value}<br>"
                        f"{self.state.xcol}=%{{x}}<br>"
                        f"{self.state.ycol}=%{{y}}<br>"
                        # f"{self.row_id_col}=%{{customdata}}<extra></extra>"
                    ),
                ))

        # Add mean and std/sem traces if enabled (include x-axis stats for split_scatter)
        if self.state.show_mean or self.state.show_std_sem:
            group_stats = self._calculate_group_stats(df_f, include_x=True)
            self._add_mean_std_traces(fig, group_stats, x_ranges, include_x_axis=True)

        # Preserve y-axis range when show_raw is off
        layout_updates = {
            "margin": dict(l=40, r=20, t=40, b=40),
            "xaxis_title": self.state.xcol,
            "yaxis_title": self.state.ycol,
            "legend_title_text": self.state.group_col,
            "showlegend": self.state.show_legend,
            "uirevision": "keep",
        }
        
        # If show_raw is off, preserve y-axis range from raw data
        # If show_raw is on, auto-scale y-axis (remove any fixed range)
        if not self.state.show_raw and y_min_raw is not None and y_max_raw is not None:
            # Add some padding
            y_padding = (y_max_raw - y_min_raw) * 0.1 if y_max_raw != y_min_raw else abs(y_max_raw) * 0.1 if y_max_raw != 0 else 1.0
            layout_updates["yaxis"] = dict(range=[y_min_raw - y_padding, y_max_raw + y_padding])
        else:
            # When show_raw is True, explicitly set yaxis to auto-scale
            layout_updates["yaxis"] = dict(autorange=True)
        
        fig.update_layout(**layout_updates)
        return fig.to_dict()

    def _figure_swarm(self, df_f: pd.DataFrame) -> dict:
        """Create swarm/strip plot with optional group coloring.
        
        Uses manual jitter by converting categorical x values to numeric positions
        and adding random horizontal offsets, similar to the demo_jitter.py pattern.
        """
        # x is categorical bins, y is per-row; optional color split via group_col
        x_cat = df_f[self.state.xcol].astype(str)
        y = self._get_y_values(df_f)
        row_ids = df_f[self.row_id_col].astype(str)

        # Get unique categorical values and create mapping to numeric positions
        unique_cats = sorted(x_cat.unique())
        cat_to_pos = {cat: i for i, cat in enumerate(unique_cats)}
        
        # Jitter parameters
        jitter_amount = 0.35  # Horizontal spread within each category
        
        fig = go.Figure()

        if self.state.group_col:
            g = df_f[self.state.group_col].astype(str)
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
                if self.state.show_raw:
                    fig.add_trace(go.Scatter(
                        x=x_jittered,
                        y=sub["y"].values,
                        mode="markers",
                        name=str(gv),
                        customdata=np.column_stack([x_cat_values, row_id_values]),
                        marker=dict(size=self.state.point_size),
                        hovertemplate=(
                            # f"roi_id={self.state.roi_id}<br>"
                            f"{self.state.xcol}=%{{customdata[0]}}<br>"
                            f"{self.state.ycol}=%{{y}}<br>"
                            f"{self.state.group_col}={gv}<br>"
                            # f"{self.row_id_col}=%{{customdata[1]}}<extra></extra>"
                        ),
                    ))
            
            # Add mean and std/sem traces if enabled (only y-axis for swarm)
            if self.state.show_mean or self.state.show_std_sem:
                group_stats = self._calculate_group_stats(df_f)
                self._add_mean_std_traces(fig, group_stats, x_ranges, include_x_axis=False)
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
            if self.state.show_raw:
                fig.add_trace(go.Scatter(
                    x=x_jittered,
                    y=tmp["y"].values,
                    mode="markers",
                    name=f"ROI {self.state.roi_id}",
                    customdata=np.column_stack([x_cat_values, row_id_values]),
                    marker=dict(size=self.state.point_size),
                    hovertemplate=(
                        # f"roi_id={self.state.roi_id}<br>"
                        f"{self.state.xcol}=%{{customdata[0]}}<br>"
                        f"{self.state.ycol}=%{{y}}<br>"
                        # f"{self.row_id_col}=%{{customdata[1]}}<extra></extra>"
                    ),
                ))

        # Set up x-axis with categorical labels at integer positions
        layout_updates = {
            "margin": dict(l=40, r=20, t=40, b=90),
            "xaxis_title": self.state.xcol,
            "yaxis_title": self.state.ycol,
            "showlegend": self.state.show_legend,
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
        if not self.state.show_raw:
            if self.state.group_col:
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

    def _figure_grouped(self, df_f: pd.DataFrame) -> dict:
        """Create grouped aggregation plot showing statistics by group."""
        if not self.state.group_col:
            return self._figure_scatter(df_f)

        g = df_f[self.state.group_col].astype(str)
        y = self._get_y_values(df_f)
        tmp = pd.DataFrame({"group": g, "y": y}).dropna(subset=["group"])

        stat = self.state.ystat
        if stat == "count":
            agg = tmp.groupby("group", dropna=False)["y"].count()
        else:
            # y is already numeric from _get_y_values, but ensure it's numeric for aggregation
            tmp["y"] = pd.to_numeric(tmp["y"], errors="coerce")
            agg = getattr(tmp.groupby("group", dropna=False)["y"], stat)()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=agg.index.astype(str).tolist(),
            y=agg.values.tolist(),
            mode="markers+lines",
            name=f"ROI {self.state.roi_id}",
        ))
        fig.update_layout(
            margin=dict(l=40, r=20, t=40, b=80),
            xaxis_title=self.state.group_col,
            yaxis_title=f"{stat}({self.state.ycol})",
            xaxis_tickangle=-30,
            showlegend=self.state.show_legend,
            uirevision="keep",
        )
        return fig.to_dict()

    def _figure_cumulative_histogram(self, df_f: pd.DataFrame) -> dict:
        """Create cumulative histogram plot with one curve per group.
        
        For each unique value in group_col, computes a cumulative histogram
        of x values, normalized to 0-1 range within each category.
        """
        if not self.state.group_col:
            logger.warning("Cumulative histogram requires a group/color column. Falling back to scatter plot.")
            return self._figure_scatter(df_f)

        x = pd.to_numeric(df_f[self.state.xcol], errors="coerce")
        g = df_f[self.state.group_col].astype(str)
        
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
                    f"{self.state.group_col}={group_value}<br>"
                    f"{self.state.xcol}=%{{x}}<br>"
                    f"Cumulative proportion=%{{y:.3f}}<extra></extra>"
                ),
            ))

        fig.update_layout(
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis_title=self.state.xcol,
            yaxis_title="Cumulative Proportion (normalized 0-1)",
            legend_title_text=self.state.group_col,
            showlegend=self.state.show_legend,
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