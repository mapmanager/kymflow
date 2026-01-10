"""Plotting functions for stall analysis.

This module provides matplotlib and plotly plotting functions for visualizing
stalls detected in velocity data. These functions handle only plotting and do
not perform stall detection (separation of concerns).
"""

from __future__ import annotations

from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import plotly.graph_objects as go

from kymflow.core.analysis.stall_analysis import Stall
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.plotting.theme import ThemeMode, get_theme_colors, get_theme_template
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def plot_stalls_matplotlib(
    kym_image: KymImage,
    roi_id: int,
    stalls: list[Stall],
    use_time_axis: bool = False,
    remove_outliers: bool = False,
    median_filter: int = 0,
    figsize: tuple[float, float] = (10, 6),
) -> plt.Figure:
    """Plot velocity data with stall overlays using matplotlib.

    This function plots velocity vs bin number (or time) and overlays filled
    rectangles for each stall. It does NOT perform stall detection - stalls
    must be computed separately and passed in.

    Args:
        kym_image: KymImage instance containing the data.
        roi_id: Identifier of the ROI to plot.
        stalls: List of Stall objects to overlay on the plot.
        use_time_axis: If True, x-axis shows time (s) instead of bin number.
            Uses kym_image.seconds_per_line for conversion.
        remove_outliers: If True, remove outliers using 2*std threshold when
            getting velocity data.
        median_filter: Median filter window size. 0 = disabled, >0 = enabled.
        figsize: Figure size as (width, height) in inches.

    Returns:
        Matplotlib Figure object.

    Raises:
        ValueError: If roi_id has no analysis data available.
    """
    # Get KymAnalysis from KymImage
    kym_analysis = kym_image.get_kym_analysis()

    # Check if analysis exists
    if not kym_analysis.has_analysis(roi_id):
        # Create empty figure with message
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(
            0.5,
            0.5,
            "No analysis data available for this ROI",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_xlabel("Bin" if not use_time_axis else "Time (s)")
        ax.set_ylabel("Velocity (mm/s)")
        return fig

    # Get velocity data
    velocity = kym_analysis.get_analysis_value(
        roi_id, "velocity", remove_outliers, median_filter
    )
    if velocity is None:
        # Create empty figure with message
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(
            0.5,
            0.5,
            "No velocity data available for this ROI",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_xlabel("Bin" if not use_time_axis else "Time (s)")
        ax.set_ylabel("Velocity (mm/s)")
        return fig

    # Create x-axis values
    if use_time_axis:
        # Use time values from analysis if available, otherwise convert from bins
        time_values = kym_analysis.get_analysis_value(
            roi_id, "time", remove_outliers, median_filter
        )
        if time_values is None:
            # Fallback: convert bins to time
            bin_indices = np.arange(len(velocity))
            x_values = bin_indices * kym_image.seconds_per_line
        else:
            x_values = time_values
        x_label = "Time (s)"
    else:
        # Use bin indices
        x_values = np.arange(len(velocity))
        x_label = "Bin"

    # Create figure and axis
    fig, ax = plt.subplots(figsize=figsize)

    # Plot velocity line
    ax.plot(x_values, velocity, "b-", linewidth=1.5, label="Velocity")

    # Calculate y-axis range for stall rectangles
    # Use velocity min/max with some padding, handling NaN values
    valid_velocity = velocity[~np.isnan(velocity)]
    if len(valid_velocity) > 0:
        y_min = np.nanmin(velocity) - 0.1 * (np.nanmax(velocity) - np.nanmin(velocity))
        y_max = np.nanmax(velocity) + 0.1 * (np.nanmax(velocity) - np.nanmin(velocity))
    else:
        # All NaN values - use default range
        y_min = -1
        y_max = 1

    # Add stall rectangles
    for stall in stalls:
        # Get x-coordinates for this stall
        if use_time_axis:
            # Convert bin indices to time
            if time_values is None:
                x_start = stall.bin_start * kym_image.seconds_per_line
                x_stop = stall.bin_stop * kym_image.seconds_per_line
            else:
                # Use actual time values from analysis (handle potential length mismatch)
                if stall.bin_start < len(time_values) and stall.bin_stop < len(
                    time_values
                ):
                    x_start = time_values[stall.bin_start]
                    x_stop = time_values[stall.bin_stop]
                else:
                    # Fallback to conversion
                    x_start = stall.bin_start * kym_image.seconds_per_line
                    x_stop = stall.bin_stop * kym_image.seconds_per_line
        else:
            x_start = float(stall.bin_start)
            x_stop = float(stall.bin_stop)

        # Create rectangle (width extends from start to stop, inclusive)
        width = x_stop - x_start
        # Add 1 to width to make it inclusive (stall.bin_stop is inclusive)
        if not use_time_axis:
            width += 1.0
        # For time axis, width is already correct

        rect = mpatches.Rectangle(
            (x_start, y_min),
            width,
            y_max - y_min,
            linewidth=0,
            edgecolor="none",
            facecolor="red",
            alpha=0.3,  # Semi-transparent
        )
        ax.add_patch(rect)

    # Set axis labels
    ax.set_xlabel(x_label)
    ax.set_ylabel("Velocity (mm/s)")
    ax.set_title(f"Velocity with Stalls (ROI {roi_id})")

    # Add grid
    ax.grid(True, alpha=0.3)

    # Add legend
    if stalls:
        # Add custom legend entry for stalls
        stall_patch = mpatches.Patch(color="red", alpha=0.3, label="Stalls")
        ax.legend(handles=[stall_patch], loc="best")
    else:
        ax.legend(loc="best")

    plt.tight_layout()
    return fig


def plot_stalls_plotly(
    kym_image: KymImage,
    roi_id: int,
    stalls: list[Stall],
    use_time_axis: bool = False,
    remove_outliers: bool = False,
    median_filter: int = 0,
    theme: Optional[ThemeMode] = None,
) -> go.Figure:
    """Plot velocity data with stall overlays using plotly.

    This function plots velocity vs bin number (or time) and overlays filled
    rectangles for each stall. It does NOT perform stall detection - stalls
    must be computed separately and passed in.

    Args:
        kym_image: KymImage instance containing the data.
        roi_id: Identifier of the ROI to plot.
        stalls: List of Stall objects to overlay on the plot.
        use_time_axis: If True, x-axis shows time (s) instead of bin number.
            Uses kym_image.seconds_per_line for conversion.
        remove_outliers: If True, remove outliers using 2*std threshold when
            getting velocity data.
        median_filter: Median filter window size. 0 = disabled, >0 = enabled.
        theme: Theme mode (DARK or LIGHT). Defaults to LIGHT if None.

    Returns:
        Plotly Figure object.
    """
    # Default to LIGHT theme
    if theme is None:
        theme = ThemeMode.LIGHT

    template = get_theme_template(theme)
    bg_color, fg_color = get_theme_colors(theme)
    font_dict = {"color": fg_color}
    grid_color = "rgba(255,255,255,0.2)" if theme is ThemeMode.DARK else "#cccccc"

    # Get KymAnalysis from KymImage
    kym_analysis = kym_image.get_kym_analysis()

    # Handle missing analysis
    if not kym_analysis.has_analysis(roi_id):
        fig = go.Figure()
        fig.add_annotation(
            text="No analysis data available for this ROI",
            showarrow=False,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            font=font_dict,
        )
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            xaxis_title="Bin" if not use_time_axis else "Time (s)",
            yaxis_title="Velocity (mm/s)",
        )
        return fig

    # Get velocity data
    velocity = kym_analysis.get_analysis_value(
        roi_id, "velocity", remove_outliers, median_filter
    )
    if velocity is None:
        fig = go.Figure()
        fig.add_annotation(
            text="No velocity data available for this ROI",
            showarrow=False,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            font=font_dict,
        )
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            xaxis_title="Bin" if not use_time_axis else "Time (s)",
            yaxis_title="Velocity (mm/s)",
        )
        return fig

    # Create x-axis values
    if use_time_axis:
        # Use time values from analysis if available, otherwise convert from bins
        time_values = kym_analysis.get_analysis_value(
            roi_id, "time", remove_outliers, median_filter
        )
        if time_values is None:
            # Fallback: convert bins to time
            bin_indices = np.arange(len(velocity))
            x_values = bin_indices * kym_image.seconds_per_line
        else:
            x_values = time_values
        x_label = "Time (s)"
    else:
        # Use bin indices
        x_values = np.arange(len(velocity))
        x_label = "Bin"

    # Create figure
    fig = go.Figure()

    # Add velocity trace
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=velocity,
            mode="lines",
            name="Velocity",
            line=dict(color="blue", width=1.5),
        )
    )

    # Add stall rectangles as shapes
    shapes = []
    for stall in stalls:
        # Get x-coordinates for this stall
        if use_time_axis:
            # Convert bin indices to time
            if time_values is None:
                x_start = stall.bin_start * kym_image.seconds_per_line
                x_stop = stall.bin_stop * kym_image.seconds_per_line
            else:
                # Use actual time values from analysis (handle potential length mismatch)
                if stall.bin_start < len(time_values) and stall.bin_stop < len(
                    time_values
                ):
                    x_start = time_values[stall.bin_start]
                    x_stop = time_values[stall.bin_stop]
                else:
                    # Fallback to conversion
                    x_start = stall.bin_start * kym_image.seconds_per_line
                    x_stop = stall.bin_stop * kym_image.seconds_per_line
        else:
            x_start = float(stall.bin_start)
            x_stop = float(stall.bin_stop)
            # For bin axis, make the rectangle inclusive (extend by 1)
            x_stop += 1.0

        # Calculate y-axis range (will be filled to axis limits)
        # We'll use yref="paper" to span full height, or calculate from velocity
        valid_velocity = velocity[~np.isnan(velocity)]
        if len(valid_velocity) > 0:
            y_min = np.nanmin(velocity)
            y_max = np.nanmax(velocity)
            y_padding = 0.1 * (y_max - y_min) if y_max != y_min else 0.1
            y_bottom = y_min - y_padding
            y_top = y_max + y_padding
        else:
            y_bottom = -1
            y_top = 1

        # Add rectangle shape
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="y",
                x0=x_start,
                y0=y_bottom,
                x1=x_stop,
                y1=y_top,
                fillcolor="red",
                opacity=0.3,
                layer="above",  # Render above the line
                line_width=0,
            )
        )

    # Update layout
    fig.update_layout(
        template=template,
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=font_dict,
        xaxis_title=x_label,
        yaxis_title="Velocity (mm/s)",
        title=f"Velocity with Stalls (ROI {roi_id})",
        shapes=shapes,
        showlegend=False,
        xaxis=dict(
            showgrid=True,
            gridcolor=grid_color,
            color=fg_color,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=grid_color,
            color=fg_color,
        ),
    )

    return fig
