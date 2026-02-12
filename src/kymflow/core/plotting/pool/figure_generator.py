"""Plotly figure generation for pool plotting application.

This module provides the FigureGenerator class for creating Plotly figure dictionaries
from data and plot state, separating figure generation logic from UI/controller concerns.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from kymflow.core.utils.logging import get_logger
from kymflow.core.plotting.pool.plot_state import PlotType, PlotState
from kymflow.core.plotting.pool.dataframe_processor import DataFrameProcessor
from kymflow.core.plotting.pool.plot_helpers import is_categorical_column

logger = get_logger(__name__)

# Selected (linked) points color — change here to switch:
SELECTED_POINTS_COLOR = "rgba(0, 200, 255, 0.9)"   # cyan
# SELECTED_POINTS_COLOR = "rgba(255, 220, 0, 0.9)"  # yellow (alternative)

# Plotly marker symbols for scatter plots
# These are used when color_grouping is set to differentiate groups by symbol
PLOTLY_SYMBOLS = [
    "circle", "square", "diamond", "triangle-up", "triangle-down",
    "triangle-left", "triangle-right", "pentagon", "hexagon", "hexagon2",
    "octagon", "star", "hexagram", "star-triangle-up", "star-triangle-down",
    "star-square", "star-diamond", "diamond-tall", "diamond-wide", "hourglass",
    "bowtie", "circle-cross", "circle-x", "square-cross", "square-x",
    "diamond-cross", "diamond-x", "cross", "x", "triangle-ne",
]


class FigureGenerator:
    """Generates Plotly figure dictionaries from data and plot state.
    
    Encapsulates all Plotly figure generation logic, including different plot types
    (scatter, swarm, grouped, histogram, cumulative_histogram) and statistical
    overlays (mean/std/sem traces).
    
    Attributes:
        data_processor: DataFrameProcessor instance for data operations.
        row_id_col: Column name containing unique row identifiers.
    """
    
    def __init__(
        self,
        data_processor: DataFrameProcessor,
        row_id_col: str = "path",
    ) -> None:
        """Initialize FigureGenerator with data processor and row ID column.
        
        Args:
            data_processor: DataFrameProcessor instance for data operations.
            row_id_col: Column name containing unique row identifiers.
        """
        self.data_processor = data_processor
        self.row_id_col = row_id_col

    def make_figure(
        self,
        df_f: pd.DataFrame,
        state: PlotState,
        *,
        selected_row_ids: Optional[set[str]] = None,
    ) -> dict:
        """Generate Plotly figure dictionary based on plot state.
        
        Args:
            df_f: Filtered dataframe (already filtered by ROI).
            state: PlotState to use for generating the figure.
            selected_row_ids: If set, these row_ids are shown as selected (linked selection).
            
        Returns:
            Plotly figure dictionary.
        """
        logger.info(
            f"FigureGenerator.make_figure: plot_type={state.plot_type.value}, "
            f"filtered_rows={len(df_f)}, roi_id={state.roi_id}, "
            f"xcol={state.xcol}, ycol={state.ycol}"
        )

        if state.plot_type == PlotType.GROUPED:
            result = self._figure_grouped(df_f, state)
        elif state.plot_type == PlotType.SCATTER:
            result = self._figure_split_scatter(df_f, state, selected_row_ids=selected_row_ids)
        elif state.plot_type == PlotType.BOX_PLOT:
            if not state.group_col or not is_categorical_column(df_f, state.group_col):
                logger.warning(
                    f"Box plot requires categorical group_col for x-axis; group_col={state.group_col} is not categorical. "
                    "Falling back to scatter."
                )
                result = self._figure_split_scatter(df_f, state, selected_row_ids=selected_row_ids)
            else:
                result = self._figure_box(df_f, state)
        elif state.plot_type == PlotType.VIOLIN:
            if not state.group_col or not is_categorical_column(df_f, state.group_col):
                logger.warning(
                    f"Violin plot requires categorical group_col for x-axis; group_col={state.group_col} is not categorical. "
                    "Falling back to scatter."
                )
                result = self._figure_split_scatter(df_f, state, selected_row_ids=selected_row_ids)
            else:
                result = self._figure_violin(df_f, state)
        elif state.plot_type == PlotType.SWARM:
            if not state.group_col or not is_categorical_column(df_f, state.group_col):
                logger.warning(
                    f"Swarm plot requires categorical group_col for x-axis; group_col={state.group_col} is not categorical. "
                    "Falling back to scatter."
                )
                result = self._figure_split_scatter(df_f, state, selected_row_ids=selected_row_ids)
            else:
                result = self._figure_swarm(df_f, state, selected_row_ids=selected_row_ids)
        elif state.plot_type == PlotType.HISTOGRAM:
            result = self._figure_histogram(df_f, state)
        elif state.plot_type == PlotType.CUMULATIVE_HISTOGRAM:
            result = self._figure_cumulative_histogram(df_f, state)
        else:
            # Fallback (e.g. unknown type): use scatter
            result = self._figure_split_scatter(df_f, state, selected_row_ids=selected_row_ids)
        
        logger.debug(f"Figure generated: {len(result.get('data', []))} traces")
        return result

    def _is_numeric_axis(self, df_f: pd.DataFrame, col: str) -> bool:
        """Return True if the column is numeric (int/float) for axis range interpretation."""
        if col not in df_f.columns:
            return False
        kind = getattr(df_f[col].dtype, "kind", None)
        return kind in {"i", "u", "f"}

    def get_axis_x_for_selection(self, df_f: pd.DataFrame, state: PlotState) -> pd.Series:
        """Return x values in the same coordinate system as the plot axis (for range/lasso selection).

        - Scatter / Split scatter, numeric x: data values as float.
        - Scatter / Split scatter, categorical x: category indices 0, 1, 2, ... (sorted order).
        - Swarm: category index + deterministic jitter (same as in _figure_swarm).
        - Box/Violin: use group_col for categorical mapping (not xcol).

        Caller must use this series with the same df_f index when masking.
        """
        if state.plot_type == PlotType.SWARM:
            return self._swarm_axis_x(df_f, state)
        if state.plot_type == PlotType.SCATTER:
            return self._scatter_axis_x(df_f, state)
        if state.plot_type in (PlotType.BOX_PLOT, PlotType.VIOLIN):
            # Use group_col for x-axis categorical mapping
            return self._scatter_axis_x_for_group_col(df_f, state)
        # Fallback for other types (e.g. GROUPED) - return numeric 0-based index
        return pd.Series(range(len(df_f)), index=df_f.index, dtype=float)

    def _scatter_axis_x(self, df_f: pd.DataFrame, state: PlotState) -> pd.Series:
        """X axis values for scatter: numeric as float (with optional abs), categorical as 0,1,2,..."""
        if self._is_numeric_axis(df_f, state.xcol):
            return self.data_processor.get_x_values(
                df_f, state.xcol, state.use_absolute_value,
                state.use_remove_values, state.remove_values_threshold
            )
        x_series = df_f[state.xcol]
        unique_cats = sorted(x_series.dropna().astype(str).unique())
        cat_to_pos = {c: i for i, c in enumerate(unique_cats)}
        return x_series.astype(str).map(cat_to_pos).astype(float)

    def _swarm_axis_x(self, df_f: pd.DataFrame, state: PlotState) -> pd.Series:
        """X axis values for swarm: category index + deterministic jitter (match _figure_swarm).
        
        Uses group_col for x-axis, color_grouping for nested grouping, and state.swarm_jitter_amount.
        Matches the jitter logic in _figure_swarm for consistent selection behavior.
        Includes group offset to match visual positioning.
        """
        # Use group_col for x-axis (categorical grouping)
        x_cat = df_f[state.group_col].astype(str)
        unique_cats = sorted(x_cat.unique())
        cat_to_pos = {cat: i for i, cat in enumerate(unique_cats)}
        jitter_amount = state.swarm_jitter_amount
        
        if state.color_grouping and state.color_grouping in df_f.columns:
            # Get all unique color values to calculate offset per group (match _figure_swarm)
            unique_colors = sorted(df_f[state.color_grouping].astype(str).unique())
            num_colors = len(unique_colors)
            group_offset_amount = state.swarm_group_offset  # Match the offset used in _figure_swarm
            
            # Nested grouping: jitter per (x_category, color_group) combination
            # Use one RNG per (x_category, color_group) for varied jitter within each group
            parts = []
            for color_idx, (color_value, sub) in enumerate(df_f.groupby(state.color_grouping, sort=True)):
                x_cat_sub = sub[state.group_col].astype(str)
                jittered_list = []
                
                # Calculate offset for this color group (match _figure_swarm)
                if num_colors > 1:
                    group_offset = (color_idx - (num_colors - 1) / 2) * group_offset_amount
                else:
                    group_offset = 0.0
                
                for x_cat_val in x_cat_sub.unique():
                    mask = x_cat_sub == x_cat_val
                    x_pos_subset = x_cat_sub[mask].map(cat_to_pos).values
                    x_cat_val_str = str(x_cat_val)
                    
                    # Create one RNG per (x_category, color_group) for deterministic but varied jitter
                    seed = hash(f"{x_cat_val_str}_{color_value}") % (2**31)
                    rng = np.random.default_rng(seed=seed)
                    # Generate jitter for all points in this (x_category, color_group)
                    jitter_values = rng.uniform(-jitter_amount / 2, jitter_amount / 2, size=len(x_pos_subset))
                    # Add group offset to match visual positioning
                    jittered_list.extend(x_pos_subset + jitter_values + group_offset)
                
                parts.append(pd.Series(jittered_list, index=sub.index))
            return pd.concat(parts).sort_index()
        
        # No color_grouping - single trace
        jittered_list = []
        for x_cat_val in x_cat.unique():
            mask = x_cat == x_cat_val
            x_pos_subset = x_cat[mask].map(cat_to_pos).values
            x_cat_val_str = str(x_cat_val)
            
            # Create one RNG per x category for deterministic but varied jitter
            seed = hash(x_cat_val_str) % (2**31)
            rng = np.random.default_rng(seed=seed)
            # Generate jitter for all points in this x category
            jitter_values = rng.uniform(-jitter_amount / 2, jitter_amount / 2, size=len(x_pos_subset))
            jittered_list.extend(x_pos_subset + jitter_values)
        
        return pd.Series(jittered_list, index=df_f.index)

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
            include_x_axis: If True, also add x-axis mean/std/sem (for scatter).
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
            
            # Add x-axis mean and std/sem for scatter (hide from legend)
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

    def _figure_scatter(
        self,
        df_f: pd.DataFrame,
        state: PlotState,
        *,
        selected_row_ids: Optional[set[str]] = None,
    ) -> dict:
        """Create scatter plot figure.
        
        Args:
            df_f: Filtered dataframe.
            state: PlotState to use for configuration.
            selected_row_ids: If set, indices of these row_ids are passed as selectedpoints.
        """
        x = self.data_processor.get_x_values(
            df_f, state.xcol, state.use_absolute_value,
            state.use_remove_values, state.remove_values_threshold
        )
        y = self.data_processor.get_y_values(
            df_f, state.ycol, state.use_absolute_value,
            state.use_remove_values, state.remove_values_threshold
        )
        row_ids = df_f[self.row_id_col].astype(str)

        selectedpoints = None
        selected = None
        if selected_row_ids:
            selectedpoints = [i for i, r in enumerate(row_ids) if r in selected_row_ids]
            if selectedpoints:
                selected = dict(
                    marker=dict(size=state.point_size * 1.3, color=SELECTED_POINTS_COLOR),
                )

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode="markers",
            name=f"ROI {state.roi_id}",
            customdata=row_ids,
            marker=dict(size=state.point_size),
            selectedpoints=selectedpoints,
            selected=selected,
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

    def _figure_split_scatter(
        self,
        df_f: pd.DataFrame,
        state: PlotState,
        *,
        selected_row_ids: Optional[set[str]] = None,
    ) -> dict:
        """Create scatter plot with color coding by group_col and symbol by color_grouping.
        
        Uses Plotly's native color and symbol parameters:
        - color: from group_col (like px.scatter with color="grandparent_folder")
        - symbol: from color_grouping (like px.scatter with symbol="roi_id")
        
        Args:
            df_f: Filtered dataframe.
            state: PlotState to use for configuration.
            selected_row_ids: If set, indices of these row_ids are passed as selectedpoints.
        """
        # If no group_col, use basic scatter
        if not state.group_col:
            return self._figure_scatter(df_f, state, selected_row_ids=selected_row_ids)

        x = self.data_processor.get_x_values(
            df_f, state.xcol, state.use_absolute_value,
            state.use_remove_values, state.remove_values_threshold
        )
        y = self.data_processor.get_y_values(
            df_f, state.ycol, state.use_absolute_value,
            state.use_remove_values, state.remove_values_threshold
        )
        row_ids = df_f[self.row_id_col].astype(str)

        # Prepare color grouping (from group_col)
        color_values = df_f[state.group_col].astype(str) if state.group_col in df_f.columns else None
        
        # Prepare symbol grouping (from color_grouping)
        symbol_values = None
        if state.color_grouping and state.color_grouping in df_f.columns:
            symbol_values = df_f[state.color_grouping].astype(str)

        # Create dataframe with all needed columns
        tmp_dict = {"x": x, "y": y, "row_id": row_ids}
        if color_values is not None:
            tmp_dict["color"] = color_values
        if symbol_values is not None:
            tmp_dict["symbol"] = symbol_values
        
        tmp = pd.DataFrame(tmp_dict).dropna(subset=["x", "y"])

        fig = go.Figure()

        # Calculate y-axis range from raw data (for preserving range when show_raw is off)
        y_min_raw = float(tmp["y"].min()) if len(tmp) > 0 else None
        y_max_raw = float(tmp["y"].max()) if len(tmp) > 0 else None

        # Calculate x ranges for each group (for mean/std positioning)
        # Group by color (group_col) and optionally by symbol (color_grouping)
        x_ranges = {}
        if "color" in tmp.columns:
            if "symbol" in tmp.columns:
                # Group by both color and symbol
                for (color_val, symbol_val), sub in tmp.groupby(["color", "symbol"], sort=True):
                    x_min = sub["x"].min()
                    x_max = sub["x"].max()
                    try:
                        x_min_val = float(x_min)
                        x_max_val = float(x_max)
                    except (ValueError, TypeError):
                        x_min_val = 0.0
                        x_max_val = 1.0
                    group_key = f"{color_val}_{symbol_val}"
                    x_ranges[group_key] = (x_min_val, x_max_val)
            else:
                # Group by color only
                for color_val, sub in tmp.groupby("color", sort=True):
                    x_min = sub["x"].min()
                    x_max = sub["x"].max()
                    try:
                        x_min_val = float(x_min)
                        x_max_val = float(x_max)
                    except (ValueError, TypeError):
                        x_min_val = 0.0
                        x_max_val = 1.0
                    x_ranges[str(color_val)] = (x_min_val, x_max_val)
        else:
            # No grouping - single range
            x_min = tmp["x"].min()
            x_max = tmp["x"].max()
            try:
                x_min_val = float(x_min)
                x_max_val = float(x_max)
            except (ValueError, TypeError):
                x_min_val = 0.0
                x_max_val = 1.0
            x_ranges["all"] = (x_min_val, x_max_val)

        # Only add raw data trace if show_raw is True
        if state.show_raw:
            # Prepare marker dict with color and/or symbol
            marker_dict = dict(size=state.point_size)
            
            # Add color array if group_col is set
            if "color" in tmp.columns:
                # Use Plotly's color mapping - create separate traces per color group for legend
                # This is cleaner than using color array directly
                for color_val, sub in tmp.groupby("color", sort=True):
                    # Prepare symbol array for this color group if symbol grouping is set
                    sub_marker = dict(size=state.point_size)
                    if "symbol" in sub.columns:
                        # Map symbol values to Plotly symbol names
                        unique_symbols = sorted(sub["symbol"].unique())
                        symbol_map = {sym: i % len(PLOTLY_SYMBOLS) for i, sym in enumerate(unique_symbols)}
                        sub_marker["symbol"] = [PLOTLY_SYMBOLS[symbol_map[sym]] for sym in sub["symbol"]]
                    
                    # Prepare customdata: include row_id and symbol value (if present)
                    if "symbol" in sub.columns:
                        customdata = np.column_stack([sub["row_id"], sub["symbol"]])
                    else:
                        customdata = sub["row_id"].values
                    
                    sp, sel = None, None
                    if selected_row_ids:
                        sp = [i for i, r in enumerate(sub["row_id"]) if r in selected_row_ids]
                        if sp:
                            sel = dict(
                                marker=dict(size=state.point_size * 1.3, color=SELECTED_POINTS_COLOR),
                            )
                    
                    # Build hover template
                    hover_parts = [f"{state.group_col}={color_val}"]
                    if "symbol" in sub.columns:
                        hover_parts.append(f"{state.color_grouping}=%{{customdata[1]}}")
                    hover_parts.extend([
                        f"{state.xcol}=%{{x}}",
                        f"{state.ycol}=%{{y}}"
                    ])
                    hovertemplate = "<br>".join(hover_parts) + "<extra></extra>"
                    
                    fig.add_trace(go.Scatter(
                        x=sub["x"],
                        y=sub["y"],
                        mode="markers",
                        name=str(color_val),
                        customdata=customdata,
                        marker=sub_marker,
                        selectedpoints=sp,
                        selected=sel,
                        hovertemplate=hovertemplate,
                    ))
            else:
                # No color grouping - single trace
                marker_dict = dict(size=state.point_size)
                if "symbol" in tmp.columns:
                    unique_symbols = sorted(tmp["symbol"].unique())
                    symbol_map = {sym: i % len(PLOTLY_SYMBOLS) for i, sym in enumerate(unique_symbols)}
                    marker_dict["symbol"] = [PLOTLY_SYMBOLS[symbol_map[sym]] for sym in tmp["symbol"]]
                
                # Prepare customdata: include row_id and symbol value (if present)
                if "symbol" in tmp.columns:
                    customdata = np.column_stack([tmp["row_id"], tmp["symbol"]])
                else:
                    customdata = tmp["row_id"].values
                
                sp, sel = None, None
                if selected_row_ids:
                    sp = [i for i, r in enumerate(tmp["row_id"]) if r in selected_row_ids]
                    if sp:
                        sel = dict(
                            marker=dict(size=state.point_size * 1.3, color=SELECTED_POINTS_COLOR),
                        )
                
                hover_parts = [f"{state.xcol}=%{{x}}", f"{state.ycol}=%{{y}}"]
                if "symbol" in tmp.columns:
                    hover_parts.insert(0, f"{state.color_grouping}=%{{customdata[1]}}")
                hovertemplate = "<br>".join(hover_parts) + "<extra></extra>"
                
                fig.add_trace(go.Scatter(
                    x=tmp["x"],
                    y=tmp["y"],
                    mode="markers",
                    name="Data",
                    customdata=customdata,
                    marker=marker_dict,
                    selectedpoints=sp,
                    selected=sel,
                    hovertemplate=hovertemplate,
                ))

        # Add mean and std/sem traces if enabled (include x-axis stats for scatter)
        # Only calculate group stats if group_col is set
        if (state.show_mean or state.show_std_sem) and state.group_col:
            group_stats = self.data_processor.calculate_group_stats(
                df_f, state.group_col, state.ycol, state.use_absolute_value,
                state.xcol, include_x=True,
                use_remove_values=state.use_remove_values, remove_values_threshold=state.remove_values_threshold
            )
            self._add_mean_std_traces(fig, group_stats, x_ranges, state, include_x_axis=True)

        # Preserve y-axis range when show_raw is off
        # Set legend title based on grouping
        legend_title = None
        if state.group_col:
            legend_title = state.group_col
            if state.color_grouping:
                legend_title = f"{state.group_col} / {state.color_grouping}"
        
        layout_updates = {
            "margin": dict(l=40, r=20, t=40, b=40),
            "xaxis_title": state.xcol,
            "yaxis_title": state.ycol,
            "showlegend": state.show_legend,
            "uirevision": "keep",
        }
        if legend_title:
            layout_updates["legend_title_text"] = legend_title
        
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

    def _figure_swarm(
        self,
        df_f: pd.DataFrame,
        state: PlotState,
        *,
        selected_row_ids: Optional[set[str]] = None,
    ) -> dict:
        """Create swarm/strip plot with categorical x (group_col) and optional color_grouping for nested grouping.
        
        Uses manual jitter by converting categorical x values to numeric positions
        and adding random horizontal offsets. With nested grouping, jitter is applied
        within each (x_category, color_group) combination.
        
        Args:
            df_f: Filtered dataframe.
            state: PlotState to use for configuration.
            selected_row_ids: If set, indices of these row_ids are passed as selectedpoints per trace.
        """
        # Use group_col for x-axis (categorical grouping)
        x_cat = df_f[state.group_col].astype(str)
        y = self.data_processor.get_y_values(
            df_f, state.ycol, state.use_absolute_value,
            state.use_remove_values, state.remove_values_threshold
        )
        row_ids = df_f[self.row_id_col].astype(str)

        # Get unique categorical values and create mapping to numeric positions
        unique_cats = sorted(x_cat.unique())
        cat_to_pos = {cat: i for i, cat in enumerate(unique_cats)}
        
        # Jitter parameters - use user-controllable amount
        jitter_amount = state.swarm_jitter_amount
        
        fig = go.Figure()
        
        # Build tmp dataframe with x, y, row_id, and optionally color_grouping
        tmp_data = {"x": x_cat, "y": y, "row_id": row_ids}
        if state.color_grouping and state.color_grouping in df_f.columns:
            tmp_data["color"] = df_f[state.color_grouping].astype(str)
        tmp = pd.DataFrame(tmp_data).dropna(subset=["x"])
        
        # Calculate y-axis range from raw data (for preserving range when show_raw is off)
        y_min_raw = float(tmp["y"].min()) if len(tmp) > 0 else None
        y_max_raw = float(tmp["y"].max()) if len(tmp) > 0 else None
        
        # Calculate x ranges for each trace (for mean/std positioning)
        x_ranges = {}
        
        # Group by color_grouping if set, otherwise single trace
        if state.color_grouping and "color" in tmp.columns:
            # Get all unique color values to calculate offset per group
            unique_colors = sorted(tmp["color"].unique())
            num_colors = len(unique_colors)
            # Offset amount: spread groups around center position (user-controllable)
            group_offset_amount = state.swarm_group_offset
            
            # Group by color_grouping for nested grouping
            for color_idx, (color_value, sub) in enumerate(tmp.groupby("color", sort=True)):
                # Convert categorical x to numeric positions
                x_positions = sub["x"].map(cat_to_pos).values
                
                # Calculate offset for this color group to position it side-by-side
                # Center groups around 0: if 2 groups, offsets are -0.15 and +0.15
                # If 3 groups, offsets are -0.3, 0, +0.3
                if num_colors > 1:
                    group_offset = (color_idx - (num_colors - 1) / 2) * group_offset_amount
                else:
                    group_offset = 0.0
                
                # Add jitter: use one RNG per (x_category, color_group) combination
                # Process each x category separately to apply jitter within each group
                x_jittered_list = []
                x_cat_values_list = []
                y_values_list = []
                row_id_values_list = []
                
                for x_cat_val in sub["x"].unique():
                    # Get all points for this x category within this color group
                    mask = sub["x"] == x_cat_val
                    x_pos_subset = x_positions[mask]
                    x_cat_val_str = str(x_cat_val)
                    
                    # Create one RNG per (x_category, color_group) for deterministic but varied jitter
                    seed = hash(f"{x_cat_val_str}_{color_value}") % (2**31)
                    rng = np.random.default_rng(seed=seed)
                    # Generate jitter for all points in this (x_category, color_group)
                    jitter_values = rng.uniform(-jitter_amount/2, jitter_amount/2, size=len(x_pos_subset))
                    # Add group offset to position this color group side-by-side with others
                    x_jittered_list.extend(x_pos_subset + jitter_values + group_offset)
                    x_cat_values_list.extend([x_cat_val_str] * len(x_pos_subset))
                    y_values_list.extend(sub["y"][mask].values)
                    row_id_values_list.extend(sub["row_id"][mask].values)
                
                x_jittered = np.array(x_jittered_list)
                x_cat_values = np.array(x_cat_values_list)
                y_values = np.array(y_values_list)
                row_id_values = np.array(row_id_values_list)
                
                # Store x range for each (x_category, color_group) combination
                # Include group offset in the range calculation
                for x_cat_val in sub["x"].unique():
                    mask_x = sub["x"] == x_cat_val
                    x_pos_subset = x_positions[mask_x]
                    if len(x_pos_subset) > 0:
                        x_center = float(np.mean(x_pos_subset)) + group_offset
                        # Ensure consistent string conversion for key matching
                        group_key = f"{str(x_cat_val)}_{str(color_value)}"
                        x_ranges[group_key] = (x_center - jitter_amount/2, x_center + jitter_amount/2)
                
                # Only add raw data trace if show_raw is True
                if state.show_raw:
                    sp, sel = None, None
                    if selected_row_ids:
                        sp = [i for i, r in enumerate(row_id_values) if r in selected_row_ids]
                        if sp:
                            sel = dict(
                                marker=dict(size=state.point_size * 1.3, color=SELECTED_POINTS_COLOR),
                            )
                    fig.add_trace(go.Scatter(
                        x=x_jittered,
                        y=y_values,
                        mode="markers",
                        name=str(color_value),
                        customdata=np.column_stack([x_cat_values, row_id_values]),
                        marker=dict(size=state.point_size),
                        selectedpoints=sp,
                        selected=sel,
                        hovertemplate=(
                            f"{state.group_col}=%{{customdata[0]}}<br>"
                            f"{state.ycol}=%{{y}}<br>"
                            f"{state.color_grouping}={color_value}<br>"
                        ),
                    ))
            
            # Add mean and std/sem traces if enabled (grouped by both group_col and color_grouping)
            if state.show_mean or state.show_std_sem:
                # Calculate stats per (x_category, color_group) combination
                # Ensure we iterate through all combinations that exist in the data
                group_stats = {}
                for x_cat_val in tmp["x"].unique():
                    for color_val in tmp["color"].unique():
                        mask = (tmp["x"] == x_cat_val) & (tmp["color"] == color_val)
                        y_subset = tmp.loc[mask, "y"].values
                        if len(y_subset) > 0:
                            mean_val = float(np.mean(y_subset))
                            std_val = float(np.std(y_subset, ddof=1))
                            sem_val = std_val / np.sqrt(len(y_subset)) if len(y_subset) > 1 else 0.0
                            # Ensure consistent string conversion for key matching with x_ranges
                            group_key = f"{str(x_cat_val)}_{str(color_val)}"
                            group_stats[group_key] = {
                                "mean": mean_val,
                                "std": std_val,
                                "sem": sem_val,
                            }
                # Debug: log if we're missing any x_ranges
                missing_ranges = set(group_stats.keys()) - set(x_ranges.keys())
                if missing_ranges:
                    logger.warning(f"Missing x_ranges for group_stats keys: {missing_ranges}")
                self._add_mean_std_traces(fig, group_stats, x_ranges, state, include_x_axis=False)
        else:
            # No color_grouping - single trace
            # Convert categorical x to numeric positions
            x_positions = tmp["x"].map(cat_to_pos).values
            # Add jitter: use one RNG per x category for deterministic but varied jitter
            x_jittered_list = []
            x_cat_values_list = []
            y_values_list = []
            row_id_values_list = []
            
            for x_cat_val in tmp["x"].unique():
                # Get all points for this x category
                mask = tmp["x"] == x_cat_val
                x_pos_subset = x_positions[mask]
                x_cat_val_str = str(x_cat_val)
                
                # Create one RNG per x category for deterministic but varied jitter
                seed = hash(x_cat_val_str) % (2**31)
                rng = np.random.default_rng(seed=seed)
                # Generate jitter for all points in this x category
                jitter_values = rng.uniform(-jitter_amount/2, jitter_amount/2, size=len(x_pos_subset))
                x_jittered_list.extend(x_pos_subset + jitter_values)
                x_cat_values_list.extend([x_cat_val_str] * len(x_pos_subset))
                y_values_list.extend(tmp["y"][mask].values)
                row_id_values_list.extend(tmp["row_id"][mask].values)
            
            x_jittered = np.array(x_jittered_list)
            x_cat_values = np.array(x_cat_values_list)
            y_values = np.array(y_values_list)
            row_id_values = np.array(row_id_values_list)
            
            # Calculate x ranges for mean/std positioning (per x category)
            x_ranges = {}
            for x_cat_val in tmp["x"].unique():
                mask = tmp["x"] == x_cat_val
                x_pos_subset = x_positions[mask]
                if len(x_pos_subset) > 0:
                    x_center = float(np.mean(x_pos_subset))
                    x_ranges[str(x_cat_val)] = (x_center - jitter_amount/2, x_center + jitter_amount/2)
            
            # Add mean and std/sem traces if enabled (grouped by group_col)
            if state.show_mean or state.show_std_sem:
                group_stats = self.data_processor.calculate_group_stats(
                    df_f, state.group_col, state.ycol, state.use_absolute_value,
                    None, include_x=False,
                    use_remove_values=state.use_remove_values, remove_values_threshold=state.remove_values_threshold
                )
                self._add_mean_std_traces(fig, group_stats, x_ranges, state, include_x_axis=False)
            
            # Only add raw data trace if show_raw is True
            if state.show_raw:
                sp, sel = None, None
                if selected_row_ids:
                    sp = [i for i, r in enumerate(row_id_values) if r in selected_row_ids]
                    if sp:
                        sel = dict(
                            marker=dict(size=state.point_size * 1.3, color=SELECTED_POINTS_COLOR),
                        )
                fig.add_trace(go.Scatter(
                    x=x_jittered,
                    y=y_values,
                    mode="markers",
                    name=f"ROI {state.roi_id}" if state.roi_id else "All ROIs",
                    customdata=np.column_stack([x_cat_values, row_id_values]),
                    marker=dict(size=state.point_size),
                    selectedpoints=sp,
                    selected=sel,
                    hovertemplate=(
                        f"{state.group_col}=%{{customdata[0]}}<br>"
                        f"{state.ycol}=%{{y}}<br>"
                    ),
                ))

        # Set up x-axis with categorical labels at integer positions
        layout_updates = {
            "margin": dict(l=40, r=20, t=40, b=90),
            "xaxis_title": state.group_col,
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
        
        # Preserve y-axis range when show_raw is off
        if not state.show_raw and y_min_raw is not None and y_max_raw is not None:
            y_padding = (y_max_raw - y_min_raw) * 0.1 if y_max_raw != y_min_raw else abs(y_max_raw) * 0.1 if y_max_raw != 0 else 1.0
            layout_updates["yaxis"] = dict(range=[y_min_raw - y_padding, y_max_raw + y_padding])
        else:
            # When show_raw is True, explicitly set yaxis to auto-scale
            layout_updates["yaxis"] = dict(autorange=True)
        
        fig.update_layout(**layout_updates)
        return fig.to_dict()

    def _figure_box(self, df_f: pd.DataFrame, state: PlotState) -> dict:
        """Create box plot with categorical x (group_col) and numeric y. Optional color_grouping for nested grouping."""
        # Use group_col for x-axis (categorical grouping)
        x = df_f[state.group_col].astype(str)
        y = self.data_processor.get_y_values(
            df_f, state.ycol, state.use_absolute_value,
            state.use_remove_values, state.remove_values_threshold
        )
        tmp = pd.DataFrame({"x": x, "y": y}).dropna(subset=["x", "y"])

        fig = go.Figure()
        # Use Plotly's offsetgroup for nested grouping to prevent overlapping
        if state.color_grouping and state.color_grouping in df_f.columns:
            # Add color column to tmp dataframe
            color_values = df_f.loc[tmp.index, state.color_grouping].astype(str)
            tmp["color"] = color_values
            tmp = tmp.dropna(subset=["color"])
            # Use alignmentgroup and offsetgroup to separate boxes by color within each x category
            for color_val, sub in tmp.groupby("color", sort=True):
                fig.add_trace(go.Box(
                    x=sub["x"],
                    y=sub["y"],
                    name=str(color_val),
                    alignmentgroup="x",  # Align boxes at same x position
                    offsetgroup=str(color_val),  # Offset boxes by color group for side-by-side display
                    boxpoints="outliers",
                    jitter=0.3,
                    pointpos=-1.8,
                    marker=dict(size=4),
                    line=dict(width=1.5),
                    showlegend=state.show_legend,
                ))
            layout_legend_title = state.color_grouping
        else:
            fig.add_trace(go.Box(
                x=tmp["x"],
                y=tmp["y"],
                name=f"ROI {state.roi_id}" if state.roi_id else "All ROIs",
                boxpoints="outliers",
                jitter=0.3,
                pointpos=-1.8,
                marker=dict(size=4),
                line=dict(width=1.5),
                showlegend=state.show_legend,
            ))
            layout_legend_title = None
        layout = dict(
            margin=dict(l=40, r=20, t=40, b=80),
            xaxis_title=state.group_col,
            yaxis_title=state.ycol,
            showlegend=state.show_legend,
            xaxis=dict(tickangle=-30),
            uirevision="keep",
        )
        # Enable grouped mode for side-by-side boxes when using color_grouping
        if state.color_grouping and state.color_grouping in df_f.columns:
            layout["boxmode"] = "group"
        if layout_legend_title:
            layout["legend_title_text"] = layout_legend_title
        fig.update_layout(**layout)
        return fig.to_dict()

    def _figure_violin(self, df_f: pd.DataFrame, state: PlotState) -> dict:
        """Create violin plot with categorical x (group_col) and numeric y. Optional color_grouping for nested grouping."""
        # Use group_col for x-axis (categorical grouping)
        x = df_f[state.group_col].astype(str)
        y = self.data_processor.get_y_values(
            df_f, state.ycol, state.use_absolute_value,
            state.use_remove_values, state.remove_values_threshold
        )
        tmp = pd.DataFrame({"x": x, "y": y}).dropna(subset=["x", "y"])

        fig = go.Figure()
        # Use Plotly's offsetgroup for nested grouping to prevent overlapping
        if state.color_grouping and state.color_grouping in df_f.columns:
            # Add color column to tmp dataframe
            color_values = df_f.loc[tmp.index, state.color_grouping].astype(str)
            tmp["color"] = color_values
            tmp = tmp.dropna(subset=["color"])
            # Use alignmentgroup and offsetgroup to separate violins by color within each x category
            for color_val, sub in tmp.groupby("color", sort=True):
                fig.add_trace(go.Violin(
                    x=sub["x"],
                    y=sub["y"],
                    name=str(color_val),
                    alignmentgroup="x",  # Align violins at same x position
                    offsetgroup=str(color_val),  # Offset violins by color group for side-by-side display
                    box_visible=True,
                    meanline_visible=True,
                    showlegend=state.show_legend,
                    line=dict(width=1.5),
                ))
            layout_legend_title = state.color_grouping
        else:
            fig.add_trace(go.Violin(
                x=tmp["x"],
                y=tmp["y"],
                name=f"ROI {state.roi_id}" if state.roi_id else "All ROIs",
                box_visible=True,
                meanline_visible=True,
                showlegend=state.show_legend,
                line=dict(width=1.5),
            ))
            layout_legend_title = None
        layout = dict(
            margin=dict(l=40, r=20, t=40, b=80),
            xaxis_title=state.group_col,
            yaxis_title=state.ycol,
            showlegend=state.show_legend,
            xaxis=dict(tickangle=-30),
            uirevision="keep",
        )
        # Enable grouped mode for side-by-side violins when using color_grouping
        if state.color_grouping and state.color_grouping in df_f.columns:
            layout["violinmode"] = "group"
        if layout_legend_title:
            layout["legend_title_text"] = layout_legend_title
        fig.update_layout(**layout)
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
        y = self.data_processor.get_y_values(
            df_f, state.ycol, state.use_absolute_value,
            state.use_remove_values, state.remove_values_threshold
        )
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
        """Create cumulative histogram: one curve when group is (none), else one curve per group.

        Uses x column (with optional abs); each curve is normalized to 0-1 within its group (or overall if no group).
        """
        x = self.data_processor.get_x_values(
            df_f, state.xcol, state.use_absolute_value,
            state.use_remove_values, state.remove_values_threshold
        ).dropna()
        if len(x) == 0:
            logger.warning("No valid data for cumulative histogram. Falling back to scatter plot.")
            return self._figure_scatter(df_f, state)

        fig = go.Figure()
        n_bins = 50

        if not state.group_col:
            # Single cumulative histogram over all x
            x_values = x.values
            counts, bin_edges = np.histogram(x_values, bins=n_bins)
            cumsum = np.cumsum(counts)
            cumsum_normalized = cumsum / cumsum[-1] if cumsum[-1] > 0 else cumsum
            x_plot = np.concatenate([[bin_edges[0]], bin_edges[1:]])
            y_plot = np.concatenate([[0], cumsum_normalized])
            fig.add_trace(go.Scatter(
                x=x_plot,
                y=y_plot,
                mode="lines",
                name=f"ROI {state.roi_id}",
                line=dict(shape="hv"),
                hovertemplate=f"{state.xcol}=%{{x}}<br>Cumulative proportion=%{{y:.3f}}<extra></extra>",
            ))
            legend_title = None
        else:
            g = df_f.loc[x.index, state.group_col].astype(str)
            tmp = pd.DataFrame({"x": x, "g": g}).dropna(subset=["g"])
            if len(tmp) == 0:
                return self._figure_scatter(df_f, state)
            for group_value, sub in tmp.groupby("g", sort=True):
                x_values = sub["x"].values
                if len(x_values) == 0:
                    continue
                counts, bin_edges = np.histogram(x_values, bins=n_bins)
                cumsum = np.cumsum(counts)
                cumsum_normalized = cumsum / cumsum[-1] if cumsum[-1] > 0 else cumsum
                x_plot = np.concatenate([[bin_edges[0]], bin_edges[1:]])
                y_plot = np.concatenate([[0], cumsum_normalized])
                fig.add_trace(go.Scatter(
                    x=x_plot,
                    y=y_plot,
                    mode="lines",
                    name=str(group_value),
                    line=dict(shape="hv"),
                    hovertemplate=(
                        f"{state.group_col}={group_value}<br>"
                        f"{state.xcol}=%{{x}}<br>Cumulative proportion=%{{y:.3f}}<extra></extra>"
                    ),
                ))
            legend_title = state.group_col

        layout = dict(
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis_title=state.xcol,
            yaxis_title="Cumulative Proportion (normalized 0-1)",
            showlegend=state.show_legend,
            uirevision="keep",
        )
        if legend_title:
            layout["legend_title_text"] = legend_title
        fig.update_layout(**layout)
        return fig.to_dict()

    def _figure_histogram(self, df_f: pd.DataFrame, state: PlotState) -> dict:
        """Create histogram of x column (with optional abs): one hist when group is (none), else one trace per group."""
        x = self.data_processor.get_x_values(
            df_f, state.xcol, state.use_absolute_value,
            state.use_remove_values, state.remove_values_threshold
        ).dropna()
        if len(x) == 0:
            logger.warning("No valid data for histogram. Falling back to scatter plot.")
            return self._figure_scatter(df_f, state)

        fig = go.Figure()

        if not state.group_col:
            fig.add_trace(go.Histogram(
                x=x.values,
                name=f"ROI {state.roi_id}",
                nbinsx=50,
                showlegend=state.show_legend,
            ))
            legend_title = None
        else:
            g = df_f.loc[x.index, state.group_col].astype(str)
            tmp = pd.DataFrame({"x": x, "g": g}).dropna(subset=["g"])
            if len(tmp) == 0:
                return self._figure_scatter(df_f, state)
            for group_value, sub in tmp.groupby("g", sort=True):
                fig.add_trace(go.Histogram(
                    x=sub["x"].values,
                    name=str(group_value),
                    nbinsx=50,
                    opacity=0.6,
                    showlegend=state.show_legend,
                ))
            legend_title = state.group_col

        layout = dict(
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis_title=state.xcol,
            yaxis_title="Count",
            barmode="overlay",
            showlegend=state.show_legend,
            uirevision="keep",
        )
        if legend_title:
            layout["legend_title_text"] = legend_title
        fig.update_layout(**layout)
        return fig.to_dict()
