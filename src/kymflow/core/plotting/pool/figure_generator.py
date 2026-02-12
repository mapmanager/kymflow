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

logger = get_logger(__name__)


class FigureGenerator:
    """Generates Plotly figure dictionaries from data and plot state.
    
    Encapsulates all Plotly figure generation logic, including different plot types
    (scatter, split_scatter, swarm, grouped, cumulative_histogram) and statistical
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
        elif state.plot_type == PlotType.SPLIT_SCATTER:
            result = self._figure_split_scatter(df_f, state, selected_row_ids=selected_row_ids)
        elif state.plot_type == PlotType.SWARM:
            result = self._figure_swarm(df_f, state, selected_row_ids=selected_row_ids)
        elif state.plot_type == PlotType.CUMULATIVE_HISTOGRAM:
            result = self._figure_cumulative_histogram(df_f, state)
        else:
            result = self._figure_scatter(df_f, state, selected_row_ids=selected_row_ids)
        
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

        Caller must use this series with the same df_f index when masking.
        """
        if state.plot_type == PlotType.SWARM:
            return self._swarm_axis_x(df_f, state)
        if state.plot_type in (PlotType.SCATTER, PlotType.SPLIT_SCATTER):
            return self._scatter_axis_x(df_f, state)
        # Fallback for other types (e.g. GROUPED) - return numeric 0-based index
        return pd.Series(range(len(df_f)), index=df_f.index, dtype=float)

    def _scatter_axis_x(self, df_f: pd.DataFrame, state: PlotState) -> pd.Series:
        """X axis values for scatter/split_scatter: numeric as float, categorical as 0,1,2,..."""
        x_series = df_f[state.xcol]
        if self._is_numeric_axis(df_f, state.xcol):
            return pd.to_numeric(x_series, errors="coerce")
        unique_cats = sorted(x_series.dropna().astype(str).unique())
        cat_to_pos = {c: i for i, c in enumerate(unique_cats)}
        return x_series.astype(str).map(cat_to_pos).astype(float)

    def _swarm_axis_x(self, df_f: pd.DataFrame, state: PlotState) -> pd.Series:
        """X axis values for swarm: category index + deterministic jitter (match _figure_swarm)."""
        x_cat = df_f[state.xcol].astype(str)
        unique_cats = sorted(x_cat.unique())
        cat_to_pos = {cat: i for i, cat in enumerate(unique_cats)}
        jitter_amount = 0.35
        if state.group_col and state.group_col in df_f.columns:
            parts = []
            for gv, sub in df_f.groupby(state.group_col, sort=True):
                x_positions = sub[state.xcol].astype(str).map(cat_to_pos).values
                seed = hash(str(gv)) % (2**31)
                rng = np.random.default_rng(seed=seed)
                jitter = rng.uniform(-jitter_amount / 2, jitter_amount / 2, size=len(x_positions))
                parts.append(pd.Series(x_positions + jitter, index=sub.index))
            return pd.concat(parts).sort_index()
        x_positions = x_cat.map(cat_to_pos).values
        rng = np.random.default_rng(seed=42)
        jitter = rng.uniform(-jitter_amount / 2, jitter_amount / 2, size=len(x_positions))
        return pd.Series(x_positions + jitter, index=df_f.index)

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
        x = df_f[state.xcol]
        y = self.data_processor.get_y_values(df_f, state.ycol, state.use_absolute_value)
        row_ids = df_f[self.row_id_col].astype(str)

        selectedpoints = None
        selected = None
        if selected_row_ids:
            selectedpoints = [i for i, r in enumerate(row_ids) if r in selected_row_ids]
            if selectedpoints:
                selected = dict(
                    marker=dict(size=state.point_size * 1.3, color="rgba(255, 80, 80, 0.9)"),
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
        """Create split scatter plot with color coding by group column.
        
        Args:
            df_f: Filtered dataframe.
            state: PlotState to use for configuration.
            selected_row_ids: If set, indices of these row_ids are passed as selectedpoints per trace.
        """
        if not state.group_col:
            return self._figure_scatter(df_f, state, selected_row_ids=selected_row_ids)

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
                sp, sel = None, None
                if selected_row_ids:
                    sp = [i for i, r in enumerate(sub["row_id"]) if r in selected_row_ids]
                    if sp:
                        sel = dict(
                            marker=dict(size=state.point_size * 1.3, color="rgba(255, 80, 80, 0.9)"),
                        )
                fig.add_trace(go.Scatter(
                    x=sub["x"],
                    y=sub["y"],
                    mode="markers",
                    name=str(group_value),
                    customdata=sub["row_id"],
                    marker=dict(size=state.point_size),
                    selectedpoints=sp,
                    selected=sel,
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

    def _figure_swarm(
        self,
        df_f: pd.DataFrame,
        state: PlotState,
        *,
        selected_row_ids: Optional[set[str]] = None,
    ) -> dict:
        """Create swarm/strip plot with optional group coloring.
        
        Uses manual jitter by converting categorical x values to numeric positions
        and adding random horizontal offsets, similar to the demo_jitter.py pattern.
        
        Args:
            df_f: Filtered dataframe.
            state: PlotState to use for configuration.
            selected_row_ids: If set, indices of these row_ids are passed as selectedpoints per trace.
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
                    sp, sel = None, None
                    if selected_row_ids:
                        sp = [i for i, r in enumerate(row_id_values) if r in selected_row_ids]
                        if sp:
                            sel = dict(
                                marker=dict(size=state.point_size * 1.3, color="rgba(255, 80, 80, 0.9)"),
                            )
                    fig.add_trace(go.Scatter(
                        x=x_jittered,
                        y=sub["y"].values,
                        mode="markers",
                        name=str(gv),
                        customdata=np.column_stack([x_cat_values, row_id_values]),
                        marker=dict(size=state.point_size),
                        selectedpoints=sp,
                        selected=sel,
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
                sp, sel = None, None
                if selected_row_ids:
                    sp = [i for i, r in enumerate(row_id_values) if r in selected_row_ids]
                    if sp:
                        sel = dict(
                            marker=dict(size=state.point_size * 1.3, color="rgba(255, 80, 80, 0.9)"),
                        )
                fig.add_trace(go.Scatter(
                    x=x_jittered,
                    y=tmp["y"].values,
                    mode="markers",
                    name=f"ROI {state.roi_id}",
                    customdata=np.column_stack([x_cat_values, row_id_values]),
                    marker=dict(size=state.point_size),
                    selectedpoints=sp,
                    selected=sel,
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
            return self._figure_scatter(df_f, state)

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
