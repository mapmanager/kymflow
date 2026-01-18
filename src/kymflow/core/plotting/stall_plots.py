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
) -> Optional[plt.Figure]:
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
        Matplotlib Figure object if data is available, None otherwise.
    """
    # Get KymAnalysis from KymImage
    kym_analysis = kym_image.get_kym_analysis()

    # Collect data to plot
    if not kym_analysis.has_analysis(roi_id):
        velocity = None
        x_values = None
    else:
        velocity = kym_analysis.get_analysis_value(
            roi_id, "velocity", remove_outliers, median_filter
        )
        # Get x-axis values (never filtered).
        # If we are not using the time axis, plot in array-index space (0..N-1).
        if use_time_axis:
            x_values = kym_analysis.get_analysis_value(roi_id, "time")
        elif velocity is None:
            x_values = None
        else:
            x_values = np.arange(len(velocity))

    # Validate data and return None if data is not available
    if velocity is None or x_values is None:
        return None
    
    # Ensure x_values and velocity have the same length (they should since they come from same DataFrame)
    if len(x_values) != len(velocity):
        logger.warning(f"x_values and velocity have different lengths: {len(x_values)} != {len(velocity)}")
        return None

    # Set x-axis label
    if use_time_axis:
        x_label = "Time (s)"
    else:
        x_label = "Bin"

    # Create figure and axis
    fig, ax = plt.subplots(figsize=figsize)

    if 0:
        # log the number of nan in velocity
        logger.info(f"Number of NaN values in velocity: {np.sum(np.isnan(velocity))}")
        # get the x-axis location of all nan values and log it
        nan_indices = np.where(np.isnan(velocity))[0]
        logger.info(f"x-axis location of NaN values: {nan_indices}")
        # for debugging, plot velocity nan values as circle
        # can't use velocity[nan_indices] because it will be nan
        # just use y-axis location of 0
        nan_y_values = np.zeros_like(nan_indices)
        ax.scatter(x_values[nan_indices], nan_y_values, color="red", marker="o")

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
            # Convert bin numbers to time using seconds_per_line
            x_start = float(stall.bin_start * kym_image.seconds_per_line)
            x_stop = float(stall.bin_stop * kym_image.seconds_per_line)
        else:
            # Use bin numbers directly
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
            alpha=0.6,  # Semi-transparent
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
) -> Optional[go.Figure]:
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
        Plotly Figure object if data is available, None otherwise.
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

    # Collect data to plot
    if not kym_analysis.has_analysis(roi_id):
        velocity = None
        x_values = None
    else:
        velocity = kym_analysis.get_analysis_value(
            roi_id, "velocity", remove_outliers, median_filter
        )
        # Get x-axis values (never filtered).
        # If we are not using the time axis, plot in array-index space (0..N-1).
        if use_time_axis:
            x_values = kym_analysis.get_analysis_value(roi_id, "time")
        elif velocity is None:
            x_values = None
        else:
            x_values = np.arange(len(velocity))

    # Validate data and return None if data is not available
    if velocity is None or x_values is None:
        logger.warning("No velocity or x_values data available")
        return None
    
    # Ensure x_values and velocity have the same length (they should since they come from same DataFrame)
    if len(x_values) != len(velocity):
        logger.warning(f"x_values and velocity have different lengths: {len(x_values)} != {len(velocity)}")
        return None

    # Set x-axis label
    if use_time_axis:
        x_label = "Time (s)"
    else:
        x_label = "Bin"

    # Create figure
    fig = go.Figure()

    # Plot velocity line
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=velocity,
            mode="lines",
            name="Velocity",
            line=dict(color="blue", width=1.5),
        )
    )

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

    # Add stall rectangles as shapes
    shapes = []
    for stall in stalls:
        # Get x-coordinates for this stall
        if use_time_axis:
            # Convert bin numbers to time using seconds_per_line
            x_start = float(stall.bin_start * kym_image.seconds_per_line)
            x_stop = float(stall.bin_stop * kym_image.seconds_per_line)
        else:
            # Use bin numbers directly
            x_start = float(stall.bin_start)
            x_stop = float(stall.bin_stop)

        # Create rectangle (width extends from start to stop, inclusive)
        width = x_stop - x_start
        # Add 1 to width to make it inclusive (stall.bin_stop is inclusive)
        if not use_time_axis:
            width += 1.0
        # For time axis, width is already correct
        x_stop = x_start + width

        # Add rectangle shape
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="y",
                x0=x_start,
                y0=y_min,
                x1=x_stop,
                y1=y_max,
                fillcolor="red",
                opacity=0.6,  # Semi-transparent (matching matplotlib alpha=0.6)
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
