from __future__ import annotations

from typing import Optional

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from kymflow_core.enums import ThemeMode
from kymflow_core.kym_file import KymFile, _medianFilter, _removeOutliers

from .colorscales import get_colorscale
from .theme import get_theme_colors, get_theme_template

from kymflow_core.utils.logging import get_logger

logger = get_logger(__name__)


def line_plot_plotly(
    kf: Optional[KymFile],
    x: str,
    y: str,
    remove_outliers: bool = False,
    median_filter: int = 0,
    theme: Optional[ThemeMode] = None,
) -> go.Figure:
    """Create a line plot from KymFile analysis data.

    Args:
        kf: KymFile instance, or None for empty plot
        x: Column name for x-axis data (e.g., "time")
        y: Column name for y-axis data (e.g., "velocity")
        remove_outliers: If True, remove outliers using 2*std threshold
        median_filter: Median filter window size. 0 = disabled, >0 = enabled (must be odd).
                       If even and > 0, raises ValueError.
        theme: Theme mode (DARK or LIGHT). Defaults to LIGHT if None.

    Returns:
        Plotly Figure ready for display

    Raises:
        ValueError: If median_filter > 0 and not odd
    """
    # Default to LIGHT theme
    if theme is None:
        theme = ThemeMode.LIGHT

    template = get_theme_template(theme)
    bg_color, fg_color = get_theme_colors(theme)

    # Handle None KymFile
    if kf is None:
        fig = go.Figure()
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
        )
        return fig

    # Get data from KymFile
    x_values = kf.getAnalysisValue(x)
    y_values = kf.getAnalysisValue(y)

    # Handle None data (no analysis)
    if x_values is None or y_values is None:
        fig = go.Figure()
        fig.add_annotation(
            text="Analyze flow to see velocity trace",
            showarrow=False,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            font=dict(color=fg_color),
        )
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
        )
        return fig

    # Prepare y data for filtering
    filtered_y = (
        y_values.copy() if isinstance(y_values, np.ndarray) else np.array(y_values)
    )

    # Apply filters
    if remove_outliers:
        filtered_y = _removeOutliers(filtered_y)

    if median_filter > 0:
        if median_filter % 2 == 0:
            raise ValueError(f"median_filter must be odd, got {median_filter}")
        filtered_y = _medianFilter(filtered_y, median_filter)

    # Create plot
    fig = go.Figure(
        go.Scatter(
            x=x_values,
            y=filtered_y,
            mode="lines",
        )
    )

    # Determine axis labels based on column names (defaults for now)
    x_label = "Time (s)" if x == "time" else x.replace("_", " ").title()
    y_label = "Velocity (mm/s)" if y == "velocity" else y.replace("_", " ").title()

    # Apply theme-based styling
    grid_color = "rgba(255,255,255,0.2)" if theme is ThemeMode.DARK else "#cccccc"

    fig.update_layout(
        template=template,
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=fg_color),
        xaxis=dict(
            title=x_label,
            color=fg_color,
            gridcolor=grid_color,
        ),
        yaxis=dict(
            title=y_label,
            color=fg_color,
            gridcolor=grid_color,
        ),
        margin=dict(l=50, r=10, t=10, b=40),
    )

    return fig


def plot_image_line_plotly(
    kf: Optional[KymFile],
    y: str = "velocity",
    remove_outliers: bool = False,
    median_filter: int = 0,
    theme: Optional[ThemeMode] = None,
    colorscale: str = "Gray",
    zmin: Optional[int] = None,
    zmax: Optional[int] = None,
) -> go.Figure:
    """Create a figure with two subplots: kymograph image (top) and line plot (bottom).

    The x-axes of both subplots are linked and use the same 'time' scale. The image
    x-axis is mapped to time values to align with the line plot below.

    Args:
        kf: KymFile instance, or None for empty plot
        y: Column name for y-axis data in line plot (default: "velocity")
        remove_outliers: If True, remove outliers using 2*std threshold
        median_filter: Median filter window size. 0 = disabled, >0 = enabled (must be odd).
                       If even and > 0, raises ValueError.
        theme: Theme mode (DARK or LIGHT). Defaults to LIGHT if None.
        colorscale: Plotly colorscale name (default: "Gray")
        zmin: Minimum intensity for display (optional)
        zmax: Maximum intensity for display (optional)

    Returns:
        Plotly Figure with two subplots ready for display

    Raises:
        ValueError: If median_filter > 0 and not odd
    """
    # Default to LIGHT theme
    if theme is None:
        theme = ThemeMode.LIGHT

    template = get_theme_template(theme)
    bg_color, fg_color = get_theme_colors(theme)
    grid_color = "rgba(255,255,255,0.2)" if theme is ThemeMode.DARK else "#cccccc"

    # Create subplots with 2 rows, shared x-axis
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.5, 0.5],  # Image gets 60%, line plot gets 40%
        # subplot_titles=("Kymograph", "Velocity vs Time"),
    )

    # Handle None KymFile
    if kf is None:
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font=dict(color=fg_color),
            uirevision="kymflow-plot",  # Preserve zoom/pan state
        )
        return fig

    # Get image and calculate time for image x-axis
    image = kf.ensure_image_loaded()
    header = kf.acquisition_metadata
    seconds_per_line = header.seconds_per_line or 0.001  # Default 1ms

    # Calculate image time using KymFile API
    num_lines = kf.num_lines
    image_time = None
    if image is not None and num_lines is not None:
        # Calculate time for each line: time[i] = i * seconds_per_line
        image_time = np.arange(num_lines) * seconds_per_line

    # Get analysis time values for line plot
    analysis_time_values = kf.getAnalysisValue("time")

    # Plot image in top subplot (row=1)
    if image is not None and image_time is not None and len(image_time) > 0:
        # Image shape: (num_lines, pixels_per_line)
        # After transpose in heatmap z=image.T: (pixels_per_line, num_lines)
        # X-axis corresponds to num_lines (time dimension), so we use image_time
        # Get colorscale (may be string or custom list)
        colorscale_value = get_colorscale(colorscale)

        heatmap_kwargs = {
            "z": image.T,
            "x": image_time,
            "colorscale": colorscale_value,
            "showscale": False,
        }
        if zmin is not None:
            heatmap_kwargs["zmin"] = zmin
        if zmax is not None:
            heatmap_kwargs["zmax"] = zmax

        fig.add_trace(
            go.Heatmap(**heatmap_kwargs),
            row=1,
            col=1,
        )

        # Configure top subplot axes
        fig.update_xaxes(
            # title_text="Time (s)",
            row=1,
            col=1,
            showgrid=True,
            gridcolor=grid_color,
            color=fg_color,
        )
        fig.update_yaxes(
            title_text="Position",
            row=1,
            col=1,
            showticklabels=False,
            showgrid=False,
            color=fg_color,
        )

        # trying to independently zoom x and y axis
        fig.update_layout(
            dragmode="zoom",
            modebar_add=["zoomInX", "zoomOutX", "zoomInY", "zoomOutY"],
        )
        fig.update_xaxes(constrain="range")
        fig.update_yaxes(constrain="range")

    # Get line plot data
    y_values = kf.getAnalysisValue(y) if analysis_time_values is not None else None

    # Plot line in bottom subplot (row=2)
    # Use analysis time values (always use 'time' column from analysis)
    if (
        analysis_time_values is not None
        and y_values is not None
        and len(analysis_time_values) > 0
    ):
        # Prepare y data for filtering
        filtered_y = (
            y_values.copy() if isinstance(y_values, np.ndarray) else np.array(y_values)
        )

        # Apply filters
        if remove_outliers:
            filtered_y = _removeOutliers(filtered_y)

        if median_filter > 0:
            if median_filter % 2 == 0:
                raise ValueError(f"median_filter must be odd, got {median_filter}")
            filtered_y = _medianFilter(filtered_y, median_filter)

        fig.add_trace(
            go.Scatter(
                x=analysis_time_values,
                y=filtered_y,
                mode="lines",
            ),
            row=2,
            col=1,
        )

        # Determine y-axis label
        y_label = "Velocity (mm/s)" if y == "velocity" else y.replace("_", " ").title()

        # Configure bottom subplot axes
        fig.update_xaxes(
            title_text="Time (s)",
            row=2,
            col=1,
            showgrid=True,
            gridcolor=grid_color,
            color=fg_color,
        )
        fig.update_yaxes(
            title_text=y_label,
            row=2,
            col=1,
            showgrid=True,
            gridcolor=grid_color,
            color=fg_color,
        )
    else:
        # No analysis data - show message
        fig.add_annotation(
            text="Analyze flow to see velocity trace",
            showarrow=False,
            x=0.5,
            y=0.5,
            xref="x2",
            yref="y2",
            font=dict(color=fg_color),
            row=2,
            col=1,
        )

    # Update overall layout with tight margins
    fig.update_layout(
        template=template,
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=fg_color),
        height=800,  # Taller figure for subplots
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),  # Tight margins similar to single plot
        uirevision="kymflow-plot",  # Preserve zoom/pan state when updating traces
    )

    return fig


def update_xaxis_range(fig: go.Figure, x_range: list[float]) -> None:
    """Update the x-axis range for both subplots in an image/line plotly figure."""
    # Update master axis (row=2) - this controls both subplots with shared_xaxes
    fig.update_xaxes(range=x_range, row=2, col=1)
    # Also update row=1 for explicit consistency
    fig.update_xaxes(range=x_range, row=1, col=1)


def update_colorscale(fig: go.Figure, colorscale: str) -> None:
    """Update the colorscale for the heatmap in an image/line plotly figure."""
    colorscale_value = get_colorscale(colorscale)
    fig.update_traces(
        colorscale=colorscale_value,
        selector=dict(type="heatmap"),
    )


def update_contrast(
    fig: go.Figure, zmin: Optional[int] = None, zmax: Optional[int] = None
) -> None:
    """Update the contrast (zmin/zmax) for the heatmap in an image/line plotly figure."""
    update_dict = {}
    if zmin is not None:
        update_dict["zmin"] = zmin
    if zmax is not None:
        update_dict["zmax"] = zmax

    if update_dict:
        fig.update_traces(
            **update_dict,
            selector=dict(type="heatmap"),
        )


def reset_image_zoom(fig: go.Figure, kf: Optional[KymFile]) -> None:
    """Reset the zoom to full scale for the kymograph image subplot."""
    if kf is None:
        return

    duration_seconds = kf.duration_seconds
    pixels_per_line = kf.pixels_per_line

    # logger.info(f"reset_image_zoom: duration_seconds: {duration_seconds} pixels_per_line: {pixels_per_line}")

    # Reset x-axis (time) for both subplots (they're shared)
    fig.update_xaxes(range=[0, duration_seconds], row=1, col=1)
    fig.update_xaxes(range=[0, duration_seconds], row=2, col=1)

    # Reset y-axis (position) for image subplot only
    fig.update_yaxes(range=[0, pixels_per_line - 1], row=1, col=1)
