from __future__ import annotations

from typing import Optional

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from kymflow.core.plotting.theme import ThemeMode
from kymflow.core.kym_file import KymFile
from kymflow.core.metadata import AnalysisParameters

from kymflow.core.plotting.colorscales import get_colorscale
from kymflow.core.plotting.theme import get_theme_colors, get_theme_template
from kymflow.core.plotting.roi_config import (
    ROI_COLOR_DEFAULT,
    ROI_COLOR_SELECTED,
    ROI_LINE_WIDTH,
    ROI_FILL_OPACITY,
)

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def line_plot_plotly(
    kf: Optional[KymFile],
    roi_id: int,
    x: str,
    y: str,
    remove_outliers: bool = False,
    median_filter: int = 0,
    theme: Optional[ThemeMode] = None,
) -> go.Figure:
    """Create a line plot from KymFile analysis data for a specific ROI.

    Args:
        kf: KymFile instance, or None for empty plot
        roi_id: Identifier of the ROI to plot (required).
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

    # Get data from KymAnalysis for specified ROI
    if kf is None or kf.kymanalysis is None:
        x_values = None
        y_values = None
    else:
        x_values = kf.kymanalysis.get_analysis_value(roi_id, x, remove_outliers, median_filter)
        y_values = kf.kymanalysis.get_analysis_value(roi_id, y, remove_outliers, median_filter)

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

    # Values are already filtered by get_analysis_value, no need to filter again
    filtered_y = y_values

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
    roi_id: int,
    y: str = "velocity",
    remove_outliers: bool = False,
    median_filter: int = 0,
    theme: Optional[ThemeMode] = None,
    colorscale: str = "Gray",
    zmin: Optional[int] = None,
    zmax: Optional[int] = None,
    selected_roi_id: Optional[int] = None,
) -> go.Figure:
    """Create a figure with two subplots: kymograph image (top) and line plot (bottom).

    The x-axes of both subplots are linked and use the same 'time' scale. The image
    x-axis is mapped to time values to align with the line plot below. ROI rectangles
    are overlaid on the image subplot.

    Args:
        kf: KymFile instance, or None for empty plot
        roi_id: Identifier of the ROI to plot in the line plot (required).
        y: Column name for y-axis data in line plot (default: "velocity")
        remove_outliers: If True, remove outliers using 2*std threshold
        median_filter: Median filter window size. 0 = disabled, >0 = enabled (must be odd).
                       If even and > 0, raises ValueError.
        theme: Theme mode (DARK or LIGHT). Defaults to LIGHT if None.
        colorscale: Plotly colorscale name (default: "Gray")
        zmin: Minimum intensity for display (optional)
        zmax: Maximum intensity for display (optional)
        selected_roi_id: Identifier of the selected ROI for highlighting (optional).
                         If provided, this ROI will be highlighted in yellow.

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
    image = kf.get_img_slice(channel=1)
    seconds_per_line = kf.seconds_per_line
    
    # Calculate image time using KymFile API
    num_lines = kf.num_lines
    image_time = None
    if image is not None and num_lines is not None:
        # Calculate time for each line: time[i] = i * seconds_per_line
        image_time = np.arange(num_lines) * seconds_per_line

    logger.info(f'image shape: {image.shape}')
    logger.info(f'num_lines: {num_lines}')
    logger.info(f'image time: {image_time}')
    logger.info(f'seconds_per_line: {seconds_per_line}')
    logger.info(f'num_lines: {num_lines}')
    
    # Get analysis time values for line plot (for specified ROI)
    if kf is None or kf.kymanalysis is None:
        analysis_time_values = None
        all_rois = []
    else:
        analysis_time_values = kf.kymanalysis.get_analysis_value(roi_id, "time", remove_outliers, median_filter)
        all_rois = kf.kymanalysis.get_all_rois()

    # Plot image in top subplot (row=1)
    if image is not None and image_time is not None and len(image_time) > 0:
        # Image shape: (num_lines, pixels_per_line)
        # After transpose in heatmap z=image.T: (pixels_per_line, num_lines)
        # X-axis corresponds to num_lines (time dimension), so we use image_time
        # Get colorscale (may be string or custom list)
        colorscale_value = get_colorscale(colorscale)

        heatmap_kwargs = {
            "z": image.T,  # kym images are [time, space], transpose to plot x-axis time, y-axis space
            # "z": image,
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
            showticklabels=True,
            gridcolor=grid_color,
            color=fg_color,
        )
        fig.update_yaxes(
            title_text="Position",
            row=1,
            col=1,
            showticklabels=True,
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
        
        # Add ROI rectangles overlay to image subplot
        if all_rois:
            _add_roi_overlay(
                fig,
                all_rois,
                selected_roi_id,
                image_time,
                seconds_per_line,
                row=1,
                col=1,
            )

    # Get line plot data (already filtered by get_analysis_value)
    if kf is None or kf.kymanalysis is None:
        y_values = None
    else:
        y_values = kf.kymanalysis.get_analysis_value(roi_id, y, remove_outliers, median_filter)

    # Plot line in bottom subplot (row=2)
    # Use analysis time values (always use 'time' column from analysis)
    if (
        analysis_time_values is not None
        and y_values is not None
        and len(analysis_time_values) > 0
    ):
        # Values are already filtered by get_analysis_value
        filtered_y = y_values

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


def _add_roi_overlay(
    fig: go.Figure,
    rois: list[AnalysisParameters],
    selected_roi_id: Optional[int],
    image_time: Optional[np.ndarray],
    seconds_per_line: float,
    row: int = 1,
    col: int = 1,
) -> None:
    """Add ROI rectangles as overlay shapes on the image subplot.
    
    Args:
        fig: Plotly figure to add shapes to.
        rois: List of AnalysisParameters instances to draw.
        selected_roi_id: ID of the selected ROI (will be highlighted in yellow).
        image_time: Array of time values for x-axis mapping.
        seconds_per_line: Time per line for converting line indices to time.
        row: Subplot row number (default: 1 for top subplot).
        col: Subplot column number (default: 1).
    """
    if image_time is None or len(image_time) == 0:
        return
    
    shapes = []
    annotations = []
    
    for roi in rois:
        is_selected = (selected_roi_id is not None and roi.roi_id == selected_roi_id)
        stroke_color = ROI_COLOR_SELECTED if is_selected else ROI_COLOR_DEFAULT
        
        # Convert ROI coordinates to time-space coordinates for heatmap
        # In the heatmap: z=image.T where image.shape = (num_lines, pixels_per_line)
        # After transpose: (pixels_per_line, num_lines) = (space, time)
        # X-axis (horizontal) = time dimension = line indices = ROI.top/bottom
        # Y-axis (vertical) = space dimension = pixel positions = ROI.left/right
        
        # X coordinates: map line indices to time values
        # Ensure min/max ordering for rectangle
        x0 = min(roi.top, roi.bottom) * seconds_per_line
        x1 = max(roi.top, roi.bottom) * seconds_per_line
        
        # Y coordinates: left and right are pixel positions (space dimension)
        # Ensure min/max ordering for rectangle
        y0 = min(roi.left, roi.right)
        y1 = max(roi.left, roi.right)
        
        logger.info(f'appending: x0:{x0}, x1:{x1}, y0:{y0}, y1:{y1}')
        # logger.info(f'  row:{row}, col:{col}')
        # logger.info(f'  roi:{roi}')

        # logger.info(f'  ROI_COLOR_SELECTED:{ROI_COLOR_SELECTED}')
        # logger.info(f'  ROI_COLOR_DEFAULT:{ROI_COLOR_DEFAULT}')
        # logger.info(f'  stroke_color:{stroke_color}')
        # logger.info(f'  ROI_LINE_WIDTH:{ROI_LINE_WIDTH}')
        # logger.info(f'  ROI_FILL_OPACITY:{ROI_FILL_OPACITY}')

        # stroke_color = 'red'
        line_color = 'red'

        xref = f"x{row if row > 1 else ''}"
        yref = f"y{row if row > 1 else ''}"
        logger.info(f'  row:{row}')
        logger.info(f'    xref:{xref} yref:{yref}')
        logger.info(f'    line_color:{line_color}')

        # Add rectangle shape
        shapes.append(
            dict(
                type="rect",
                xref=xref,
                yref=yref,
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                layer="above",  # ← Add this to render ROI on top of the heatmap
                line=dict(
                    color=line_color,
                    width=ROI_LINE_WIDTH,
                ),
                fillcolor=stroke_color,
                opacity=ROI_FILL_OPACITY,
            )
        )
        
        # Add label annotation (show roi_id)
        # Position label at top-left of ROI rectangle
        annotations.append(
            dict(
                x=x0,
                y=y1,  # Top of rectangle (y1 is right, but in image coords top is max y)
                text=f"ROI {roi.roi_id}",
                showarrow=False,
                xref=f"x{row if row > 1 else ''}",
                yref=f"y{row if row > 1 else ''}",
                bgcolor="rgba(255,255,255,0.7)",
                bordercolor=stroke_color,
                borderwidth=1,
                font=dict(size=10, color="black"),
                xanchor="left",
                yanchor="top",
            )
        )
    
    # Add shapes to layout
    if shapes:
        # Get existing shapes or initialize empty list
        existing_shapes = list(fig.layout.shapes) if fig.layout.shapes else []
        existing_shapes.extend(shapes)
        fig.update_layout(shapes=existing_shapes)
    
    # Add annotations to layout
    if annotations:
        # Get existing annotations or initialize empty list
        existing_annotations = list(fig.layout.annotations) if fig.layout.annotations else []
        existing_annotations.extend(annotations)
        fig.update_layout(annotations=existing_annotations)


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
