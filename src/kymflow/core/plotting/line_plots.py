from __future__ import annotations

from typing import Optional, Union

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from kymflow.core.plotting.theme import ThemeMode
from kymflow.core.image_loaders.kym_image import KymImage

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


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert hex color string to RGBA format.
    
    Args:
        hex_color: Hex color string (e.g., "#ffffff" or "#000000")
        alpha: Alpha transparency value between 0 and 1 (default: 1.0)
    
    Returns:
        RGBA color string (e.g., "rgba(255, 255, 255, 0.8)")
    """
    if not hex_color.startswith("#"):
        return hex_color
    
    hex_rgb = hex_color.lstrip("#")
    rgb = tuple(int(hex_rgb[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})"


def line_plot_plotly(
    kf: Optional[KymImage],
    roi_id: int,
    x: str,
    y: str,
    remove_outliers: bool = False,
    median_filter: int = 0,
    theme: Optional[ThemeMode] = None,
) -> go.Figure:
    """Create a line plot from KymImage analysis data for a specific ROI.

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
    font_dict = {"color": fg_color}

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
    if kf is None:
        x_values = None
        y_values = None
    else:
        kym_analysis = kf.get_kym_analysis()
        if not kym_analysis.has_analysis(roi_id):
            x_values = None
            y_values = None
        else:
            x_values = kym_analysis.get_analysis_value(roi_id, x, remove_outliers, median_filter)
            y_values = kym_analysis.get_analysis_value(roi_id, y, remove_outliers, median_filter)

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
            font=font_dict,
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
        font=font_dict,
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
    kf: Optional[KymImage],
    channel: int = 1,
    yStat: str = "velocity",
    remove_outliers: bool = False,
    median_filter: int = 0,
    colorscale: str = "Gray",
    plot_rois: bool = True,
    selected_roi_id: Optional[int] = None,
    zmin: Optional[int] = None,
    zmax: Optional[int] = None,
    theme: Optional[ThemeMode] = ThemeMode.LIGHT,
    transpose: bool = False,
) -> go.Figure:
    """Create a figure with two subplots: kymograph image (top) and line plot (bottom).

    The x-axes of both subplots are linked and use the same 'time' scale. The image
    x-axis is mapped to time values to align with the line plot below. ROI rectangles
    are overlaid on the image subplot.

    Args:
        kf: KymImage instance, or None for empty plot
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
    # if theme is None:
    #     theme = ThemeMode.LIGHT

    template = get_theme_template(theme)
    bg_color, fg_color = get_theme_colors(theme)
    font_dict = {"color": fg_color}
    grid_color = "rgba(255,255,255,0.2)" if theme is ThemeMode.DARK else "#cccccc"
    
    # Configurable plot height
    plot_height = 600  # 800

    # Create subplots with 2 rows, shared x-axis
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.6, 0.4],  # Image gets 60%, line plot gets 40%
        # subplot_titles=("Kymograph", "Velocity vs Time"),
    )

    # Common layout parameters
    layout_dict = {
        "template": template,
        "paper_bgcolor": bg_color,
        "plot_bgcolor": bg_color,
        "font": font_dict,
        "height": plot_height,
        "showlegend": False,
        "margin": dict(l=10, r=10, t=10, b=10),
        "uirevision": "kymflow-plot",
    }

    # Handle None KymFile
    if kf is None:
        fig.update_layout(**layout_dict)
        return fig

    image = kf.get_img_slice(channel=channel)

    # Early return if image is missing or invalid
    if image is None:
        fig.update_layout(**layout_dict)
        return fig

    # physical units for image axes
    dim0_arange = kf.get_dim_arange(0)  # First dimension (rows)
    dim1_arange = kf.get_dim_arange(1)  # Second dimension (columns)

    # import numpy as np
    # logger.info(f'dim0_arange: min:{np.min(dim0_arange)}, max:{np.max(dim0_arange)}')
    # logger.info(f'dim1_arange: min:{np.min(dim1_arange)}, max:{np.max(dim1_arange)}')

    # logger.info(f'image shape: {image.shape}')
    # logger.info(f'num_lines: {num_lines}')
    # logger.info(f'image time: {image_time}')
    # logger.info(f'seconds_per_line: {seconds_per_line}')
    # logger.info(f'num_lines: {num_lines}')
    
    # Plot image in top subplot (row=1)
    # Image shape: (num_lines, pixels_per_line)
    # After transpose in heatmap z=image.T: (pixels_per_line, num_lines)
    # X-axis corresponds to num_lines (time dimension), so we use image_time
    # Get colorscale (may be string or custom list)
    colorscale_value = get_colorscale(colorscale)

    heatmap_kwargs = {
        "z": image.transpose() if transpose else image,
        "x": dim0_arange if transpose else dim1_arange,
        "y": dim1_arange if transpose else dim0_arange,
        "colorscale": colorscale_value,
        "showscale": False,
        **({"zmin": zmin} if zmin is not None else {}),
        **({"zmax": zmax} if zmax is not None else {}),
    }

    fig.add_trace(
        go.Heatmap(**heatmap_kwargs),
        row=1,
        col=1,
    )

    # Configure top subplot axes using header labels
    y_label = kf.header.labels[1] if transpose else kf.header.labels[0]  # Space dimension
    fig.update_xaxes(
        title_text="",
        row=1,
        col=1,
        showgrid=True,
        showticklabels=True,
        gridcolor=grid_color,
        color=fg_color,
    )
    fig.update_yaxes(
        title_text=y_label,
        row=1,
        col=1,
        showticklabels=True,
        showgrid=False,
        color=fg_color,
    )

    # Configure zoom behavior for independent x and y axis zooming
    fig.update_layout(
        dragmode="zoom",
        modebar_add=["zoomInX", "zoomOutX", "zoomInY", "zoomOutY"],
    )
    fig.update_xaxes(constrain="range")
    fig.update_yaxes(constrain="range")
    
    # Add ROI rectangles overlay to image subplot
    if plot_rois:
        _add_roi_overlay(
            fig,
            kf,
            selected_roi_id,
            transpose,
            row=1,
            col=1,
        )

    # Plot line plot if analysis data is available
    # Get analysis data for line plot (for specified ROI)
    kym_analysis = kf.get_kym_analysis()
    if selected_roi_id is not None and kym_analysis.has_analysis(selected_roi_id):
        analysis_time_values = kym_analysis.get_analysis_value(selected_roi_id, "time")
        y_values = kym_analysis.get_analysis_value(selected_roi_id, yStat, remove_outliers, median_filter)
    else:
        analysis_time_values = None
        y_values = None

    if (
        analysis_time_values is not None
        and y_values is not None
        and len(analysis_time_values) > 0
    ):
        # import numpy as np
        # logger.info('=== add_trace()')
        # logger.info(f'analysis_time_values: n:{len(y_values)} min:{np.min(analysis_time_values)}, max:{np.max(analysis_time_values)}')
        # logger.info(f'y_values: n:{len(y_values)} min:{np.min(y_values)}, max:{np.max(y_values)}')

        fig.add_trace(
            go.Scatter(
                x=analysis_time_values,
                y=y_values,
                mode="lines",
            ),
            row=2,
            col=1,
        )

        # Determine y-axis label
        # y_label = "Velocity (mm/s)" if y == "velocity" else y.replace("_", " ").title()
        # y_label = yStat

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
            title_text=yStat,
            row=2,
            col=1,
            showgrid=True,
            gridcolor=grid_color,
            color=fg_color,
        )

        # ------------------------------------------------------------------
        # DEPRECATED: Stall analysis is deprecated
        # # Stall analysis overlays (row=2: velocity vs time)
        # #
        # # Stalls are stored on the KymAnalysis object (computed on-demand).
        # # We map stall bin indices to time using analysis_time_values and draw
        # # vertical rectangles spanning the full subplot height.
        # # ------------------------------------------------------------------
        # if selected_roi_id is not None:
        #     stall_analysis = kym_analysis.get_stall_analysis(selected_roi_id)
        # else:
        #     stall_analysis = None
        #
        # if stall_analysis is not None and stall_analysis.stalls:
        #     n_time = len(analysis_time_values)
        #     for stall in stall_analysis.stalls:
        #         if not (0 <= stall.bin_start < n_time and 0 <= stall.bin_stop < n_time):
        #             logger.warning(
        #                 "Skipping out-of-range stall for ROI %s: [%s, %s] (time_len=%s)",
        #                 selected_roi_id,
        #                 stall.bin_start,
        #                 stall.bin_stop,
        #                 n_time,
        #             )
        #             continue
        #
        #         x0 = float(analysis_time_values[stall.bin_start])
        #         x1 = float(analysis_time_values[stall.bin_stop])
        #         if x1 < x0:
        #             x0, x1 = x1, x0
        #
        #         # Use yref='y2 domain' so rectangles span the full height of row=2.
        #         fig.add_shape(
        #             type="rect",
        #             xref="x2",
        #             yref="y2 domain",
        #             x0=x0,
        #             x1=x1,
        #             y0=0,
        #             y1=1,
        #             fillcolor="cyan",
        #             opacity=0.25,
        #             line_width=0,
        #             layer="below",
        #         )
    else:
        # No analysis data - show message
        fig.add_annotation(
            text="Analyze flow to see velocity trace",
            showarrow=False,
            x=0.5,
            y=0.5,
            xref="x2",
            yref="y2",
            font=font_dict,
            row=2,
            col=1,
        )

    # Update overall layout
    fig.update_layout(**layout_dict)

    return fig


def _add_single_roi_line_plot(
    fig: go.Figure,
    kym_analysis,
    roi_id: int,
    row: int,
    yStat: str,
    remove_outliers: bool,
    median_filter: int,
    grid_color: str,
    fg_color: str,
    bg_color: str,
    font_dict: dict,
) -> None:
    """Add a line plot with stall overlays for a single ROI to a specific subplot row.
    
    Args:
        fig: Plotly figure to add the line plot to.
        kym_analysis: KymAnalysis instance to get data from.
        roi_id: ROI identifier to plot.
        row: Subplot row number (1-based).
        yStat: Column name for y-axis data (e.g., "velocity").
        remove_outliers: If True, remove outliers using 2*std threshold.
        median_filter: Median filter window size.
        grid_color: Color for grid lines.
        fg_color: Color for foreground text.
        bg_color: Background color for legend box.
        font_dict: Font dictionary for annotations.
    """
    if not kym_analysis.has_analysis(roi_id):
        # No analysis data - show message
        fig.add_annotation(
            text="Analyze flow to see velocity trace",
            showarrow=False,
            x=0.5,
            y=0.5,
            xref=f"x{row if row > 1 else ''}",
            yref=f"y{row if row > 1 else ''}",
            font=font_dict,
            row=row,
            col=1,
        )
        return
    
    analysis_time_values = kym_analysis.get_analysis_value(roi_id, "time")
    y_values = kym_analysis.get_analysis_value(roi_id, yStat, remove_outliers, median_filter)
    
    if (
        analysis_time_values is not None
        and y_values is not None
        and len(analysis_time_values) > 0
    ):
        # Add line plot trace with legend label
        fig.add_trace(
            go.Scatter(
                x=analysis_time_values,
                y=y_values,
                mode="lines",
                name=f"ROI {roi_id}",
            ),
            row=row,
            col=1,
        )

        # Configure subplot axes
        xref = f"x{row if row > 1 else ''}"
        yref = f"y{row if row > 1 else ''}"
        
        fig.update_xaxes(
            title_text="Time (s)",
            row=row,
            col=1,
            showgrid=True,
            gridcolor=grid_color,
            color=fg_color,
        )
        fig.update_yaxes(
            title_text=yStat,
            row=row,
            col=1,
            showgrid=True,
            gridcolor=grid_color,
            color=fg_color,
        )

        # Add ROI ID label in upper right corner of this subplot (like a legend)
        # Use paper coordinates (0-1) relative to this subplot's domain
        fig.add_annotation(
            text=f"ROI {roi_id}",
            showarrow=False,
            xref=f"{xref} domain",
            yref=f"{yref} domain",
            x=0.98,
            y=0.98,
            xanchor="right",
            yanchor="top",
            bgcolor=_hex_to_rgba(bg_color, alpha=0.8),
            bordercolor=fg_color,
            borderwidth=1,
            borderpad=4,
            font=dict(size=10, color=fg_color),
            row=row,
            col=1,
        )

        # DEPRECATED: Stall analysis is deprecated
        # # Add stall analysis overlays
        # logger.warning('turned of stall analysis plot')
        if 0:  # DEPRECATED: Stall analysis is deprecated
            stall_analysis = kym_analysis.get_stall_analysis(roi_id)
            if stall_analysis is not None and stall_analysis.stalls:
                n_time = len(analysis_time_values)
                for stall in stall_analysis.stalls:
                    if not (0 <= stall.bin_start < n_time and 0 <= stall.bin_stop < n_time):
                        logger.warning(
                            "Skipping out-of-range stall for ROI %s: [%s, %s] (time_len=%s)",
                            roi_id,
                            stall.bin_start,
                            stall.bin_stop,
                            n_time,
                        )
                        continue

                    x0 = float(analysis_time_values[stall.bin_start])
                    x1 = float(analysis_time_values[stall.bin_stop])
                    if x1 < x0:
                        x0, x1 = x1, x0

                    # Use yref with domain so rectangles span the full height of the row
                    fig.add_shape(
                        type="rect",
                        xref=xref,
                        yref=f"{yref} domain",
                        x0=x0,
                        x1=x1,
                        y0=0,
                        y1=1,
                        fillcolor="cyan",
                        opacity=0.25,
                        line_width=0,
                        layer="below",
                    )
    else:
        # No analysis data - show message
        fig.add_annotation(
            text="Analyze flow to see velocity trace",
            showarrow=False,
            x=0.5,
            y=0.5,
            xref=f"x{row if row > 1 else ''}",
            yref=f"y{row if row > 1 else ''}",
            font=font_dict,
            row=row,
            col=1,
        )


def _add_velocity_event_overlays(
    fig: go.Figure,
    kym_analysis,
    roi_id: int,
    analysis_time_values,
    row: int,
    span_sec_if_no_end: float = 0.20,
    selected_event_id: Optional[str] = None,
) -> None:
    """Add velocity event overlays as rectangles on a line plot subplot.
    
    Args:
        fig: Plotly figure to add shapes to.
        kym_analysis: KymAnalysis instance to get velocity events from.
        roi_id: ROI identifier to get events for.
        analysis_time_values: Time array for validation (numpy array).
        row: Subplot row number (1-based).
        span_sec_if_no_end: Fixed width in seconds when t_end is None (default: 0.20).
        selected_event_id: Optional event_id to highlight with a border (default: None).
    """
    velocity_events = kym_analysis.get_velocity_events(roi_id)
    # logger.warning(f'adding velocity events for roi {roi_id}: {len(velocity_events)}')
    if velocity_events is None or len(velocity_events) == 0:
        logger.warning(f'no velocity events for roi {roi_id}')
        return
    
    # Get time range for validation
    if analysis_time_values is None or len(analysis_time_values) == 0:
        return
    
    time_min = float(np.min(analysis_time_values))
    time_max = float(np.max(analysis_time_values))
    
    # Determine xref and yref for this row
    xref = f"x{row if row > 1 else ''}"
    yref = f"y{row if row > 1 else ''}"
    
    # Color mapping by event_type
    color_map = {
        "baseline_drop": "rgba(255, 165, 0, 0.25)",  # Orange
        "nan_gap": "rgba(255, 0, 0, 0.25)",  # Red
        "User Added": "rgba(0, 0, 255, 0.25)",  # Blue
    }
    
    for event in velocity_events:
        # Validate t_start
        t_start = float(event.t_start)
        if not np.isfinite(t_start):
            logger.warning(
                "Skipping velocity event with invalid t_start for ROI %s: t_start=%s",
                roi_id,
                event.t_start,
            )
            continue
        
        # Skip if t_start is out of bounds
        if t_start < time_min or t_start > time_max:
            logger.warning(
                "Skipping out-of-range velocity event for ROI %s: t_start=%s (time_range=[%s, %s])",
                roi_id,
                t_start,
                time_min,
                time_max,
            )
            continue
        
        # Determine t_end
        if event.t_end is None or not np.isfinite(event.t_end) or event.t_end <= t_start:
            # Use fixed span when t_end is missing or invalid
            t_end_plot = t_start + span_sec_if_no_end
        else:
            t_end_plot = float(event.t_end)
            # Clamp to time range
            if t_end_plot > time_max:
                t_end_plot = time_max
        
        # Ensure x0 < x1
        x0 = t_start
        x1 = t_end_plot
        if x1 < x0:
            x0, x1 = x1, x0
        
        # Get event_id (UUID) for this event to compare with selected
        # Find index of this event in the list
        velocity_events_list = kym_analysis.get_velocity_events(roi_id)
        if velocity_events_list is None:
            event_id = None
        else:
            try:
                event_idx = velocity_events_list.index(event)
                event_id = kym_analysis._velocity_event_uuid_reverse.get((roi_id, event_idx))
            except (ValueError, AttributeError):
                # Fallback if event not found or UUID mapping not available
                event_id = None
        is_selected = (selected_event_id is not None and event_id is not None and event_id == selected_event_id)
        
        # Get color based on event_type
        event_color = color_map.get(event.event_type, "rgba(128, 128, 128, 0.25)")  # Gray fallback
        if event.t_end is None:
            event_color = "rgba(255, 0, 0, 0.5)"

        # logger.warning(f'added velocity event for roi {roi_id}:')
        # logger.warning(f'  event_type:"{event.event_type}"')
        # logger.warning(f'  t_start:{t_start} t_end:{t_end_plot}')
        # logger.warning(f'  x0:{x0} x1:{x1} y0:0 y1:1')
        # logger.warning(f'  color:{event_color}')

        # Add rectangle shape for velocity event overlay
        shape_dict = {
            "type": "rect",
            "xref": xref,
            "yref": f"{yref} domain",
            "x0": x0,
            "x1": x1,
            "y0": 0,
            "y1": 1,
            "fillcolor": event_color,
            "layer": "below",
        }
        
        # Add border for selected event
        if is_selected:
            shape_dict["line"] = {
                "color": "yellow",  # Match ROI_COLOR_SELECTED
                "width": 2,  # Similar to ROI_LINE_WIDTH
            }
        else:
            shape_dict["line_width"] = 0
        
        fig.add_shape(**shape_dict)


# DEPRECATED: This function is deprecated. Use plot_image_line_plotly_v3() instead.
def plot_image_line_plotly_v2(
    kf: Optional[KymImage],
    channel: int = 1,
    yStat: str = "velocity",
    remove_outliers: bool = False,
    median_filter: int = 0,
    colorscale: str = "Gray",
    plot_rois: bool = True,
    selected_roi_id: Optional[Union[int, list[int]]] = None,
    zmin: Optional[int] = None,
    zmax: Optional[int] = None,
    theme: Optional[ThemeMode] = ThemeMode.LIGHT,
    transpose: bool = False,
) -> go.Figure:
    """Create a figure with kymograph image and one or more line plots for multiple ROIs.
    
    .. deprecated:: 
        This function is deprecated. Use :func:`plot_image_line_plotly_v3` instead.
    
    This is an extended version of plot_image_line_plotly that supports plotting
    line plots for multiple ROIs, each in its own subplot row with stall overlays.

    Args:
        kf: KymImage instance, or None for empty plot
        channel: Image channel to display (default: 1)
        yStat: Column name for y-axis data in line plots (default: "velocity")
        remove_outliers: If True, remove outliers using 2*std threshold
        median_filter: Median filter window size. 0 = disabled, >0 = enabled (must be odd).
                       If even and > 0, raises ValueError.
        colorscale: Plotly colorscale name (default: "Gray")
        plot_rois: If True, overlay ROI rectangles on the image
        selected_roi_id: List of ROI identifiers to plot line plots for. If None, only
                         the image is shown (no line plots).
        zmin: Minimum intensity for display (optional)
        zmax: Maximum intensity for display (optional)
        theme: Theme mode (DARK or LIGHT). Defaults to LIGHT if None.
        transpose: If True, transpose the image display

    Returns:
        Plotly Figure with image subplot and one or more line plot subplots

    Raises:
        ValueError: If median_filter > 0 and not odd
    """
    template = get_theme_template(theme)
    bg_color, fg_color = get_theme_colors(theme)
    font_dict = {"color": fg_color}
    grid_color = "rgba(255,255,255,0.2)" if theme is ThemeMode.DARK else "#cccccc"
    
    # Configurable plot height
    plot_height = 600

    # Determine number of rows: 1 for image + N for line plots
    if selected_roi_id is not None and isinstance(selected_roi_id, int):
        selected_roi_id = [selected_roi_id]
    num_line_plots = len(selected_roi_id) if selected_roi_id is not None else 0
    num_rows = 1 + num_line_plots
    
    # Calculate row heights: image gets proportionally more space, line plots share the rest
    if num_line_plots == 0:
        row_heights = [1.0]
    else:
        # Image gets 40%, line plots share the remaining 60%
        image_height = 0.4
        line_height_per_plot = 0.6 / num_line_plots
        row_heights = [image_height] + [line_height_per_plot] * num_line_plots

    # Create subplots
    fig = make_subplots(
        rows=num_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=row_heights,
    )

    # Handle None KymFile (minimal layout for early return)
    if kf is None:
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font=font_dict,
            height=plot_height,
        )
        return fig

    image = kf.get_img_slice(channel=channel)

    # Early return if image is missing or invalid (minimal layout)
    if image is None:
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font=font_dict,
            height=plot_height,
        )
        return fig

    # Physical units for image axes
    dim0_arange = kf.get_dim_arange(0)  # First dimension (rows)
    dim1_arange = kf.get_dim_arange(1)  # Second dimension (columns)
    
    # Plot image in top subplot (row=1)
    colorscale_value = get_colorscale(colorscale)

    heatmap_kwargs = {
        "z": image.transpose() if transpose else image,
        "x": dim0_arange if transpose else dim1_arange,
        "y": dim1_arange if transpose else dim0_arange,
        "colorscale": colorscale_value,
        "showscale": False,
        **({"zmin": zmin} if zmin is not None else {}),
        **({"zmax": zmax} if zmax is not None else {}),
    }

    fig.add_trace(
        go.Heatmap(**heatmap_kwargs),
        row=1,
        col=1,
    )

    # Configure top subplot axes using header labels
    x_label = kf.header.labels[0] if transpose else kf.header.labels[1]  # Time dimension
    y_label = kf.header.labels[1] if transpose else kf.header.labels[0]  # Space dimension
    fig.update_xaxes(
        title_text=x_label,
        row=1,
        col=1,
        showgrid=True,
        showticklabels=True,
        gridcolor=grid_color,
        color=fg_color,
    )
    fig.update_yaxes(
        title_text=y_label,
        row=1,
        col=1,
        showticklabels=True,
        showgrid=False,
        color=fg_color,
    )

    # Configure zoom behavior for independent x and y axis zooming
    fig.update_xaxes(constrain="range")
    fig.update_yaxes(constrain="range")
    
    # Add ROI rectangles overlay to image subplot
    # For highlighting, use the first ROI in the list if provided
    highlight_roi_id = selected_roi_id[0] if selected_roi_id else None
    if plot_rois:
        _add_roi_overlay(
            fig,
            kf,
            highlight_roi_id,
            transpose,
            row=1,
            col=1,
        )

    # Add line plots for each ROI
    if selected_roi_id is not None:
        kym_analysis = kf.get_kym_analysis()
        for idx, roi_id in enumerate(selected_roi_id):
            row_num = 2 + idx  # Row 1 is image, rows 2+ are line plots
            _add_single_roi_line_plot(
                fig,
                kym_analysis,
                roi_id,
                row_num,
                yStat,
                remove_outliers,
                median_filter,
                grid_color,
                fg_color,
                bg_color,
                font_dict,
            )

    # Build complete layout configuration once
    layout_dict = {
        "template": template,
        "paper_bgcolor": bg_color,
        "plot_bgcolor": bg_color,
        "font": font_dict,
        "height": plot_height,
        "margin": dict(l=10, r=10, t=10, b=10),
        "uirevision": "kymflow-plot",
        "dragmode": "zoom",
        "modebar_add": ["zoomInX", "zoomOutX", "zoomInY", "zoomOutY"],
        "showlegend": False,  # No global legend - each line plot has its own ROI ID label
    }

    # Apply layout once at the end
    fig.update_layout(**layout_dict)

    return fig

# abb
# @dataclass
# class XAxisCallback:
#     x0: float
#     x1: float

def plot_image_line_plotly_v3(
    kf: Optional[KymImage],
    channel: int = 1,
    yStat: str = "velocity",
    remove_outliers: bool = False,
    median_filter: int = 0,
    colorscale: str = "Gray",
    plot_rois: bool = True,
    selected_roi_id: Optional[Union[int, list[int]]] = None,
    zmin: Optional[int] = None,
    zmax: Optional[int] = None,
    theme: Optional[ThemeMode] = ThemeMode.LIGHT,
    transpose: bool = False,
    span_sec_if_no_end: float = 0.20,
    selected_event_id: Optional[str] = None,
    # x_axis_callback: Optional[Callable[[XAxisCallback], None]] = None,
) -> go.Figure:
    """Create a figure with kymograph image and one or more line plots for multiple ROIs.
    
    This is an extended version of plot_image_line_plotly_v2 that adds velocity event
    overlays as rectangles on velocity line plots, in addition to stall analysis overlays.

    Args:
        kf: KymImage instance, or None for empty plot
        channel: Image channel to display (default: 1)
        yStat: Column name for y-axis data in line plots (default: "velocity")
        remove_outliers: If True, remove outliers using 2*std threshold
        median_filter: Median filter window size. 0 = disabled, >0 = enabled (must be odd).
                       If even and > 0, raises ValueError.
        colorscale: Plotly colorscale name (default: "Gray")
        plot_rois: If True, overlay ROI rectangles on the image
        selected_roi_id: List of ROI identifiers to plot line plots for. If None, only
                         the image is shown (no line plots).
        zmin: Minimum intensity for display (optional)
        zmax: Maximum intensity for display (optional)
        theme: Theme mode (DARK or LIGHT). Defaults to LIGHT if None.
        transpose: If True, transpose the image display
        span_sec_if_no_end: Fixed width in seconds for velocity events when t_end is None
                           (default: 0.20)

    Returns:
        Plotly Figure with image subplot and one or more line plot subplots with
        both stall and velocity event overlays

    Raises:
        ValueError: If median_filter > 0 and not odd
    """
    template = get_theme_template(theme)
    bg_color, fg_color = get_theme_colors(theme)
    font_dict = {"color": fg_color}
    grid_color = "rgba(255,255,255,0.2)" if theme is ThemeMode.DARK else "#cccccc"
    
    # abb let page layout decide
    # Configurable plot height
    # plot_height = 300
    # logger.warning(f'HARD CODING plot_height: {plot_height}')

    # Determine number of rows: 1 for image + N for line plots
    if selected_roi_id is not None and isinstance(selected_roi_id, int):
        selected_roi_id = [selected_roi_id]
    num_line_plots = len(selected_roi_id) if selected_roi_id is not None else 0
    num_rows = 1 + num_line_plots
    
    logger.debug(f'pyinstaller hard coding num_line_plots=1 num_rows=2')
    num_line_plots = 1
    num_rows = 2

    # Calculate row heights: image gets proportionally more space, line plots share the rest
    if num_line_plots == 0:
        row_heights = [1.0]
    else:
        # Image gets 40%, line plots share the remaining 60%
        image_height = 0.6
        line_height_per_plot = 0.4 / num_line_plots
        row_heights = [image_height] + [line_height_per_plot] * num_line_plots

    # Create subplots
    fig = make_subplots(
        rows=num_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,  # 0.025
        row_heights=row_heights,
    )


    # Handle None KymFile (minimal layout for early return)
    if kf is None:
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font=font_dict,
            # height=plot_height,
        )
        return fig

    image = kf.get_img_slice(channel=channel)

    # Early return if image is missing or invalid (minimal layout)
    if image is None:
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font=font_dict,
            # height=plot_height,
        )
        return fig

    # Physical units for image axes
    dim0_arange = kf.get_dim_arange(0)  # First dimension (rows)
    dim1_arange = kf.get_dim_arange(1)  # Second dimension (columns)
    
    # Plot image in top subplot (row=1)
    colorscale_value = get_colorscale(colorscale)

    heatmap_kwargs = {
        "z": image.transpose() if transpose else image,
        "x": dim0_arange if transpose else dim1_arange,
        "y": dim1_arange if transpose else dim0_arange,
        "colorscale": colorscale_value,
        "showscale": False,
        **({"zmin": zmin} if zmin is not None else {}),
        **({"zmax": zmax} if zmax is not None else {}),
    }

    fig.add_trace(
        go.Heatmap(**heatmap_kwargs),
        row=1,
        col=1,
    )

    # Configure top subplot axes using header labels
    y_label = kf.header.labels[1] if transpose else kf.header.labels[0]  # Space dimension
    fig.update_xaxes(
        title_text="",  # No x-axis label on image heatmap (time label shown on line plot below)
        row=1,
        col=1,
        showgrid=False,
        showticklabels=False,
        gridcolor=grid_color,
        color=fg_color,
    )
    fig.update_yaxes(
        title_text=y_label,
        row=1,
        col=1,
        showticklabels=True,
        showgrid=False,
        color=fg_color,
    )

    # Configure zoom behavior for independent x and y axis zooming
    fig.update_xaxes(constrain="range")
    fig.update_yaxes(constrain="range")
    
    # Add ROI rectangles overlay to image subplot
    # For highlighting, use the first ROI in the list if provided
    highlight_roi_id = selected_roi_id[0] if selected_roi_id else None
    if plot_rois:
        _add_roi_overlay(
            fig,
            kf,
            highlight_roi_id,
            transpose,
            row=1,
            col=1,
        )

    # Add line plots for each ROI
    if selected_roi_id is not None:
        kym_analysis = kf.get_kym_analysis()
        for idx, roi_id in enumerate(selected_roi_id):
            row_num = 2 + idx  # Row 1 is image, rows 2+ are line plots
            
            _add_single_roi_line_plot(
                fig,
                kym_analysis,
                roi_id,
                row_num,
                yStat,
                remove_outliers,
                median_filter,
                grid_color,
                fg_color,
                bg_color,
                font_dict,
            )
            
            # Add velocity event overlays after stall overlays (so they render on top)
            # Get analysis_time_values for validation
            if kym_analysis.has_analysis(roi_id):
                analysis_time_values = kym_analysis.get_analysis_value(roi_id, "time")
                if analysis_time_values is not None:
                    _add_velocity_event_overlays(
                        fig,
                        kym_analysis,
                        roi_id,
                        np.array(analysis_time_values),
                        row_num,
                        span_sec_if_no_end,
                        selected_event_id=selected_event_id,
                    )

    # Build complete layout configuration once
    layout_dict = {
        "template": template,
        "paper_bgcolor": bg_color,
        "plot_bgcolor": bg_color,
        "font": font_dict,
        # "height": plot_height,
        "margin": dict(l=10, r=10, t=10, b=10),
        "uirevision": "kymflow-plot",
        "dragmode": "zoom",
        "modebar_add": ["zoomInX", "zoomOutX", "zoomInY", "zoomOutY"],
        "showlegend": False,  # No global legend - each line plot has its own ROI ID label
    }

    # Apply layout once at the end
    fig.update_layout(**layout_dict)

    return fig


def _add_roi_overlay(
    fig: go.Figure,
    kf: KymImage,
    selected_roi_id: Optional[int],
    transpose: bool,
    row: int = 1,
    col: int = 1,
) -> None:
    """Add ROI rectangles as overlay shapes on the image subplot.
    
    Args:
        fig: Plotly figure to add shapes to.
        kf: KymImage instance to get ROIs from.
        selected_roi_id: ID of the selected ROI (will be highlighted in yellow).
        transpose: If True, swap x/y coordinates to match transposed image.
        row: Subplot row number (default: 1 for top subplot).
        col: Subplot column number (default: 1).
    """
        
    all_rois = kf.rois.as_list()
    if not all_rois:
        return
    
    shapes = []
    annotations = []
    
    for roi in all_rois:
        is_selected = roi.id == selected_roi_id
        stroke_color = ROI_COLOR_SELECTED if is_selected else ROI_COLOR_DEFAULT
        
        # Get ROI coordinates in physical units
        # Returns RoiBoundsFloat with dim0 (time) and dim1 (space) coordinates
        bounds_physical = kf.get_roi_physical_coords(roi.id)
        
        if transpose:
            # When transposed: image is transposed, coordinates map directly
            # x-axis = dim0 (time), y-axis = dim1 (space)
            x0 = min(bounds_physical.dim0_start, bounds_physical.dim0_stop)
            x1 = max(bounds_physical.dim0_start, bounds_physical.dim0_stop)
            y0 = min(bounds_physical.dim1_start, bounds_physical.dim1_stop)
            y1 = max(bounds_physical.dim1_start, bounds_physical.dim1_stop)
        else:
            # When not transposed: need to swap coordinates
            # x-axis = dim1 (space), y-axis = dim0 (time)
            x0 = min(bounds_physical.dim1_start, bounds_physical.dim1_stop)
            x1 = max(bounds_physical.dim1_start, bounds_physical.dim1_stop)
            y0 = min(bounds_physical.dim0_start, bounds_physical.dim0_stop)
            y1 = max(bounds_physical.dim0_start, bounds_physical.dim0_stop)
        
        # logger.info(f'appending roi.id:{roi.id} x0:{x0}, x1:{x1}, y0:{y0}, y1:{y1}')

        # logger.info(f'  row:{row}, col:{col}')
        # logger.info(f'  roi:{roi}')

        # logger.info(f'  ROI_COLOR_SELECTED:{ROI_COLOR_SELECTED}')
        # logger.info(f'  ROI_COLOR_DEFAULT:{ROI_COLOR_DEFAULT}')
        # logger.info(f'  stroke_color:{stroke_color}')
        # logger.info(f'  ROI_LINE_WIDTH:{ROI_LINE_WIDTH}')
        # logger.info(f'  ROI_FILL_OPACITY:{ROI_FILL_OPACITY}')

        # stroke_color = 'red'
        # line_color = 'red'

        xref = f"x{row if row > 1 else ''}"
        yref = f"y{row if row > 1 else ''}"

        # logger.info(f'  row:{row}')
        # logger.info(f'    xref:{xref} yref:{yref}')
        # logger.info(f'    line_color:{line_color}')

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
                    color=stroke_color,
                    width=ROI_LINE_WIDTH,
                ),
                # fillcolor=stroke_color,
                opacity=ROI_FILL_OPACITY,
            )
        )
        
        # Add label annotation (show roi_id)
        # Position label at top-left of ROI rectangle
        annotations.append(
            dict(
                x=x0,
                y=y1,  # Top of rectangle (y1 is right, but in image coords top is max y)
                text=f"ROI {roi.id}",
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


def reset_image_zoom(fig: go.Figure, kf: Optional[KymImage]) -> None:
    """Reset the zoom to full scale for the kymograph image subplot."""
    if kf is None:
        return

    duration_seconds = None
    if kf.header.physical_size and len(kf.header.physical_size) > 0:
        duration_seconds = kf.header.physical_size[0]
    if duration_seconds is None:
        return
    pixels_per_line = kf.pixels_per_line

    # logger.info(f"reset_image_zoom: duration_seconds: {duration_seconds} pixels_per_line: {pixels_per_line}")

    # Reset x-axis (time) for both subplots (they're shared)
    fig.update_xaxes(range=[0, duration_seconds], row=1, col=1)
    fig.update_xaxes(range=[0, duration_seconds], row=2, col=1)

    # Reset y-axis (position) for image subplot only
    fig.update_yaxes(range=[0, pixels_per_line - 1], row=1, col=1)
