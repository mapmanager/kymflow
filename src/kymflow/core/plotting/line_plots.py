from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

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

if TYPE_CHECKING:
    from kymflow.core.analysis.velocity_events.velocity_events import VelocityEvent

logger = get_logger(__name__)


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:  # pragma: no cover
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


# FLAGGED FOR REMOVAL: line_plot_plotly() - Check if used in gui_v2 or critical notebooks before removing
def line_plot_plotly(  # pragma: no cover
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


def _add_single_roi_line_plot(  # pragma: no cover
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
) -> tuple[np.ndarray | None, np.ndarray | None]:
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
    
    Returns:
        Tuple of (time_values, y_values) arrays, or (None, None) if no analysis data.
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
        return (None, None)
    
    analysis_time_values = kym_analysis.get_analysis_value(roi_id, "time")
    y_values = kym_analysis.get_analysis_value(roi_id, yStat, remove_outliers, median_filter)
    
    if (
        analysis_time_values is not None
        and y_values is not None
        and len(analysis_time_values) > 0
    ):
        # Add line plot trace with legend label
        fig.add_trace(
            # go.Scatter(
            go.Scattergl(
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
        # Return the arrays for reuse by callers
        return (analysis_time_values, y_values)
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
        return (None, None)


def _add_velocity_event_overlays(  # pragma: no cover
    fig: go.Figure,
    kym_analysis,
    roi_id: int,
    time_bounds: tuple[float, float] | None,
    row: int,
    span_sec_if_no_end: float = 0.20,
    selected_event_id: Optional[str] = None,
    event_filter: Optional[dict[str, bool]] = None,
) -> None:
    """Add velocity event overlays as rectangles on a line plot subplot.
    
    Args:
        fig: Plotly figure to add shapes to.
        kym_analysis: KymAnalysis instance to get velocity events from.
        roi_id: ROI identifier to get events for.
        time_bounds: Time bounds (time_min, time_max) in seconds for validation.
        row: Subplot row number (1-based).
        span_sec_if_no_end: Fixed width in seconds when t_end is None (default: 0.20).
        selected_event_id: Optional event_id to highlight with a border (default: None).
        event_filter: Optional dict mapping event_type (str) to bool (True = include, False = exclude).
    """
    if event_filter is None:
        velocity_events = kym_analysis.get_velocity_events(roi_id)
    else:
        velocity_events = kym_analysis.get_velocity_events_filtered(roi_id, event_filter)
    # logger.warning(f'adding velocity events for roi {roi_id}: {len(velocity_events)}')
    if velocity_events is None or len(velocity_events) == 0:
        # logger.warning(f'no velocity events for roi {roi_id}')
        return
    
    # Get time range for validation
    if time_bounds is None:
        return
    
    time_min, time_max = time_bounds
    logger.error(f'=== time_min={time_min} time_max={time_max}')

    # Determine xref and yref for this row
    xref = f"x{row if row > 1 else ''}"
    yref = f"y{row if row > 1 else ''}"
    
    # Event overlay brightness (alpha value, 0.0 = transparent, 1.0 = opaque)
    event_overlay_alpha = 0.5
    
    # Color mapping by event_type
    color_map = {
        "baseline_drop": f"rgba(255, 0, 0, {event_overlay_alpha})",  # red
        "baseline_rise": f"rgba(0, 255, 0, {event_overlay_alpha})",  # green
        "nan_gap": f"rgba(0, 0, 255, {event_overlay_alpha})",  # blue
        "User Added": f"rgba(255, 255, 0, {event_overlay_alpha})",  # yellow
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
        
        _outlineRect = False
        # Determine t_end
        if event.t_end is None or not np.isfinite(event.t_end) or event.t_end <= t_start:
            # Use fixed span when t_end is missing or invalid
            t_end_plot = t_start + span_sec_if_no_end
            _outlineRect = True  # no t_end then use outline
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
        
        # Get event_id (UUID) from event object
        event_uuid = event._uuid if hasattr(event, '_uuid') and event._uuid else None
        if event_uuid is None:
            logger.warning(f'VelocityEvent for roi {roi_id} missing UUID, skipping name assignment')
        
        is_selected = (selected_event_id is not None and event_uuid is not None and event_uuid == selected_event_id)
        
        # Get color based on event_type
        event_color = color_map.get(event.event_type, "rgba(128, 128, 128, 0.25)")  # Gray fallback
        # if event.t_end is None:
        #     event_color = "rgba(255, 0, 0, 0.5)"

        # logger.warning(f'added velocity event for roi {roi_id}:')
        # logger.warning(f'  event_type:"{event.event_type}"')
        # logger.warning(f'  t_start:{t_start} t_end:{t_end_plot}')
        # logger.warning(f'  x0:{x0} x1:{x1} y0:0 y1:1')
        # logger.warning(f'  color:{event_color}')

        # logger.info(f'adding velocity event overlay for roi {roi_id}:')
        # logger.info(f'  event_uuid:{event_uuid}')
        # logger.info(f'  is_selected:{is_selected}')

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
            "name": event_uuid,  # UUID for CRUD operations
        }
        
        # Add border for selected event
        if is_selected:
            shape_dict["line"] = {
                "color": "yellow",  # Match ROI_COLOR_SELECTED
                "width": 2,  # Similar to ROI_LINE_WIDTH
                "dash": "dot" if _outlineRect else "solid",
            }
        else:
            shape_dict["line"] = {"width": 0}
        
        fig.add_shape(**shape_dict)


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
    event_filter: Optional[dict[str, bool]] = None,
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
        event_filter: Optional dict mapping event_type (str) to bool (True = include, False = exclude).

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
    
    # logger.debug(f'pyinstaller hard coding num_line_plots=1 num_rows=2')
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
        # go.Heatmapgl(**heatmap_kwargs),
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
            # Get time bounds for validation (computed from ROI coordinates, no analysis needed)
            time_bounds = kym_analysis.get_time_bounds(roi_id)
            if time_bounds is not None:
                _add_velocity_event_overlays(
                    fig,
                    kym_analysis,
                    roi_id,
                    time_bounds,
                    row_num,
                    span_sec_if_no_end,
                    selected_event_id=selected_event_id,
                    event_filter=event_filter,
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


def _add_roi_overlay(  # pragma: no cover
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


def update_xaxis_range_v2(plotly_dict: dict, x_range: list[float]) -> None:  # pragma: no cover
    """Update the x-axis range for both subplots in a plotly figure dict representation.
    
    Args:
        plotly_dict: Plotly figure dictionary (from fig.to_dict()).
        x_range: List of two floats [min, max] for the x-axis range.
    """
    if 'layout' not in plotly_dict:
        return
    
    layout = plotly_dict['layout']
    
    # Update xaxis (row 1 - image subplot)
    if 'xaxis' in layout:
        layout['xaxis']['range'] = x_range
    
    # Update xaxis2 (row 2 - line plot subplot) if it exists
    if 'xaxis2' in layout:
        layout['xaxis2']['range'] = x_range

    # return plotly_dict


def update_yaxis_range_v2(plotly_dict: dict, y_range: list[float], row: int = 1) -> None:  # pragma: no cover
    """Update the y-axis range for a specific subplot row in a plotly figure dict representation.
    
    Args:
        plotly_dict: Plotly figure dictionary (from fig.to_dict()).
        y_range: List of two floats [min, max] for the y-axis range.
        row: Subplot row number (1-based). Default is 1 (image subplot).
    """
    if 'layout' not in plotly_dict:
        return
    
    layout = plotly_dict['layout']
    
    # Determine yaxis key based on row number
    if row == 1:
        yaxis_key = 'yaxis'
    else:
        yaxis_key = f'yaxis{row}'
    
    # Update yaxis for the specified row
    if yaxis_key in layout:
        layout[yaxis_key]['range'] = y_range


# ============================================================================
# CRUD functions for kym event rects in plotly dict
# ============================================================================

def _find_kym_event_rect_by_uuid(plotly_dict: dict, event_uuid: str, row: int = 2) -> Optional[tuple[int, dict]]:
    """Find a kym event rect shape by UUID in plotly dict.
    
    Args:
        plotly_dict: Plotly figure dictionary to search.
        event_uuid: UUID string to find.
        row: Subplot row number (default: 2 for line plot).
    
    Returns:
        Tuple of (shape_index, shape_dict) if found, None otherwise.
    """
    if 'layout' not in plotly_dict:
        return None
    
    layout = plotly_dict['layout']
    if 'shapes' not in layout or not layout['shapes']:
        return None
    
    # Determine xref and yref for this row
    xref = f"x{row if row > 1 else ''}"
    yref = f"y{row if row > 1 else ''}"
    
    shapes = layout['shapes']
    for idx, shape in enumerate(shapes):
        # Validate shape is a rect
        if shape.get('type') != 'rect':
            continue
        
        # Check if xref/yref match this row
        if shape.get('xref') != xref:
            continue
        if shape.get('yref') != f"{yref} domain":
            continue
        
        # Check if name matches UUID
        if shape.get('name') == event_uuid:
            return (idx, shape)
    
    return None


def _calculate_event_rect_coords(
    event: "VelocityEvent",
    time_range: tuple[float, float],
    span_sec_if_no_end: float = 0.20,
) -> tuple[float, float]:
    """Calculate x0, x1 coordinates for an event rect.
    
    Args:
        event: VelocityEvent to calculate coordinates for.
        time_range: Tuple of (time_min, time_max) for clamping in physical units.
        span_sec_if_no_end: Fixed width when t_end is None.
    
    Returns:
        Tuple of (x0, x1) coordinates.
    
    Raises:
        ValueError: If time_range is None or invalid.
    """
    if time_range is None:
        raise ValueError("time_range is None - cannot calculate event rect coordinates")
    
    time_min, time_max = time_range
    if not np.isfinite(time_min) or not np.isfinite(time_max) or time_min >= time_max:
        raise ValueError(f"Invalid time_range: {time_range}")
    
    t_start = float(event.t_start)
    
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
    
    return (x0, x1)


def add_kym_event_rect(
    plotly_dict: dict,
    event: "VelocityEvent",
    time_range: tuple[float, float],
    row: int = 2,
    span_sec_if_no_end: float = 0.20,
    event_filter: Optional[dict[str, bool]] = None,
) -> None:
    """Add a kym event rect shape to plotly dict.
    
    Args:
        plotly_dict: Plotly figure dictionary to modify.
        event: VelocityEvent to add.
        time_range: Tuple of (time_min, time_max) for coordinate calculation and clamping.
        row: Subplot row number (default: 2 for line plot).
        span_sec_if_no_end: Fixed width when t_end is None.
        event_filter: Optional event type filter (for color mapping, currently unused).
    
    Raises:
        ValueError: If time_range is None or invalid.
    """
    if 'layout' not in plotly_dict:
        logger.error("add_kym_event_rect: plotly_dict missing 'layout' key")
        return
    
    layout = plotly_dict['layout']
    
    # Check event has UUID
    if not hasattr(event, '_uuid') or not event._uuid:
        logger.error("add_kym_event_rect: event missing UUID")
        return
    
    event_uuid = event._uuid
    
    # Check UUID not already present
    existing = _find_kym_event_rect_by_uuid(plotly_dict, event_uuid, row)
    if existing is not None:
        logger.error(f"add_kym_event_rect: rect with UUID {event_uuid} already exists in row {row}")
        return
    
    # Calculate coordinates
    x0, x1 = _calculate_event_rect_coords(event, time_range, span_sec_if_no_end)
    
    # Determine xref and yref for this row
    xref = f"x{row if row > 1 else ''}"
    yref = f"y{row if row > 1 else ''}"
    
    # Get event color (same logic as _add_velocity_event_overlays)
    event_overlay_alpha = 0.5
    color_map = {
        "baseline_drop": f"rgba(255, 0, 0, {event_overlay_alpha})",  # red
        "baseline_rise": f"rgba(0, 255, 0, {event_overlay_alpha})",  # green
        "nan_gap": f"rgba(0, 0, 255, {event_overlay_alpha})",  # blue
        "User Added": f"rgba(255, 255, 0, {event_overlay_alpha})",  # yellow
    }
    event_color = color_map.get(event.event_type, "rgba(128, 128, 128, 0.25)")  # Gray fallback
    
    # Create shape_dict
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
        "name": event_uuid,
        "line": {"width": 0},  # Non-selected by default (no outline)
    }
    
    # Initialize shapes list if needed
    if 'shapes' not in layout:
        layout['shapes'] = []
    elif layout['shapes'] is None:
        layout['shapes'] = []
    
    # Append to shapes list
    layout['shapes'].append(shape_dict)


def delete_kym_event_rect(plotly_dict: dict, event_uuid: str, row: int = 2) -> None:
    """Delete a kym event rect shape from plotly dict by UUID.
    
    Args:
        plotly_dict: Plotly figure dictionary to modify.
        event_uuid: UUID of the event rect to delete.
        row: Subplot row number (default: 2).
    """
    if 'layout' not in plotly_dict:
        logger.error("delete_kym_event_rect: plotly_dict missing 'layout' key")
        return
    
    layout = plotly_dict['layout']
    if 'shapes' not in layout or not layout['shapes']:
        logger.error(f"delete_kym_event_rect: no shapes found for UUID {event_uuid}")
        return
    
    # Find the shape
    result = _find_kym_event_rect_by_uuid(plotly_dict, event_uuid, row)
    if result is None:
        logger.error(f"delete_kym_event_rect: rect with UUID {event_uuid} not found in row {row}")
        return
    
    shape_idx, _ = result
    
    # Remove from shapes list
    layout['shapes'].pop(shape_idx)


def move_kym_event_rect(
    plotly_dict: dict,
    event: "VelocityEvent",
    time_range: tuple[float, float],
    row: int = 2,
    span_sec_if_no_end: float = 0.20,
) -> None:
    """Move/update a kym event rect shape coordinates in plotly dict.
    
    Args:
        plotly_dict: Plotly figure dictionary to modify.
        event: VelocityEvent with updated coordinates.
        time_range: Tuple of (time_min, time_max) for coordinate calculation and clamping.
        row: Subplot row number (default: 2).
        span_sec_if_no_end: Fixed width when t_end is None.
    
    Raises:
        ValueError: If time_range is None or invalid.
    """
    if 'layout' not in plotly_dict:
        logger.error("move_kym_event_rect: plotly_dict missing 'layout' key")
        return
    
    # Check event has UUID
    if not hasattr(event, '_uuid') or not event._uuid:
        logger.error("move_kym_event_rect: event missing UUID")
        return
    
    event_uuid = event._uuid
    
    # Find the shape
    result = _find_kym_event_rect_by_uuid(plotly_dict, event_uuid, row)
    if result is None:
        logger.error(f"move_kym_event_rect: rect with UUID {event_uuid} not found in row {row}")
        return
    
    shape_idx, shape_dict = result
    
    # Calculate new coordinates
    x0, x1 = _calculate_event_rect_coords(event, time_range, span_sec_if_no_end)
    
    # Update coordinates (preserve other properties)
    layout = plotly_dict['layout']
    layout['shapes'][shape_idx]['x0'] = x0
    layout['shapes'][shape_idx]['x1'] = x1


def clear_kym_event_rects(plotly_dict: dict, row: int = 2) -> None:
    """Clear all kym event rect shapes from plotly dict.
    
    Args:
        plotly_dict: Plotly figure dictionary to modify.
        row: Subplot row number (default: 2).
    """
    if 'layout' not in plotly_dict:
        logger.error("clear_kym_event_rects: plotly_dict missing 'layout' key")
        return
    
    layout = plotly_dict['layout']
    if 'shapes' not in layout or not layout['shapes']:
        return
    
    # Determine xref and yref for this row
    xref = f"x{row if row > 1 else ''}"
    yref = f"y{row if row > 1 else ''}"
    
    # Filter out UUID-named rects for this row
    shapes = layout['shapes']
    filtered_shapes = []
    for shape in shapes:
        # Keep shape if it's not a UUID-named rect for this row
        if shape.get('type') == 'rect':
            if shape.get('xref') == xref and shape.get('yref') == f"{yref} domain":
                if 'name' in shape and shape.get('name'):  # Has UUID name
                    continue  # Skip this shape (it's a kym event rect)
        # Keep all other shapes
        filtered_shapes.append(shape)
    
    layout['shapes'] = filtered_shapes


def refresh_kym_event_rects(
    plotly_dict: dict,
    kym_analysis,
    roi_id: int,
    time_range: tuple[float, float],
    row: int = 2,
    event_filter: Optional[dict[str, bool]] = None,
    selected_event_id: Optional[str] = None,
) -> None:
    """Clear and re-add all kym event rects from kymanalysis to plotly dict.

    This is used for CRUD-style updates when the event filter changes.

    Args:
        plotly_dict: Plotly figure dictionary to modify.
        kym_analysis: KymAnalysis instance to get events from.
        roi_id: ROI identifier to get events for.
        time_range: Tuple of (time_min, time_max) for coordinate calculation and clamping.
        row: Subplot row number (default: 2 for line plot).
        event_filter: Optional dict mapping event_type (str) to bool (True = include, False = exclude).
        selected_event_id: Optional UUID string of currently selected event; if not
            visible after filtering, selection will be cleared.
    """
    # Clear existing event rects
    clear_kym_event_rects(plotly_dict, row=row)

    # Get filtered or unfiltered events
    if event_filter is None:
        velocity_events = kym_analysis.get_velocity_events(roi_id)
    else:
        velocity_events = kym_analysis.get_velocity_events_filtered(roi_id, event_filter)

    if velocity_events is None:
        # Nothing to draw; also clear selection
        select_kym_event_rect(plotly_dict, None, row=row)
        return

    # Add back visible events
    for event in velocity_events:
        add_kym_event_rect(
            plotly_dict,
            event,
            time_range,
            row=row,
        )

    # Restore selection if selected_event_id is still visible; otherwise deselect all.
    selected_event = None
    if selected_event_id is not None:
        for event in velocity_events:
            if event._uuid == selected_event_id:
                selected_event = event
                break

    select_kym_event_rect(plotly_dict, selected_event, row=row)


def select_kym_event_rect(
    plotly_dict: dict,
    event: Optional["VelocityEvent"],
    row: int = 2,
) -> None:
    """Select a kym event rect by setting yellow outline, deselect others.
    
    Args:
        plotly_dict: Plotly figure dictionary to modify.
        event: VelocityEvent to select (None to deselect all).
        row: Subplot row number (default: 2).
    """
    if 'layout' not in plotly_dict:
        # logger.error("select_kym_event_rect: plotly_dict missing 'layout' key")
        return
    
    layout = plotly_dict['layout']
    if 'shapes' not in layout or not layout['shapes']:
        return
    
    # Determine xref and yref for this row
    xref = f"x{row if row > 1 else ''}"
    yref = f"y{row if row > 1 else ''}"
    
    # Get target UUID from event._uuid
    target_uuid = event._uuid if event is not None and hasattr(event, '_uuid') and event._uuid else None

    # Determine dash style for selected event
    use_dash = False
    if event is not None:
        if event.t_end is None or not np.isfinite(event.t_end) or event.t_end <= event.t_start:
            use_dash = True
    
    # Iterate all shapes and update selection state
    # IMPORTANT: Modify layout['shapes'][idx] directly, not through an intermediate variable
    # This ensures changes are made to the actual plotly_dict structure
    _foundTarget = False
    shape_uuids_found = []
    for idx, shape in enumerate(layout['shapes']):
        # Only process UUID-named rects for this row
        if shape.get('type') != 'rect':
            continue
        if shape.get('xref') != xref:
            continue
        if shape.get('yref') != f"{yref} domain":
            continue
        if 'name' not in shape or not shape.get('name'):
            # logger.error(f'no name found for shape: {shape}')
            continue  # Not a UUID-named rect
        
        shape_uuid = shape.get('name')
        shape_uuids_found.append(shape_uuid)

        if target_uuid is not None and shape_uuid == target_uuid:
            # Selected: set yellow outline
            # Modify directly in plotly_dict structure
            _foundTarget = True
            layout['shapes'][idx]['line'] = {
                "color": "yellow",
                "width": 2,
                "dash": "dot" if use_dash else "solid",
            }
        else:
            # Non-selected: remove outline (set width to 0)
            # Modify directly in plotly_dict structure
            layout['shapes'][idx]['line'] = {"width": 0}

    if not _foundTarget:
        logger.error(f'select_kym_event_rect: no target found for event: {event} target_uuid={target_uuid}')


def update_xaxis_range(fig: go.Figure, x_range: list[float]) -> None:  # pragma: no cover
    """Update the x-axis range for both subplots in an image/line plotly figure."""
    # Update master axis (row=2) - this controls both subplots with shared_xaxes
    fig.update_xaxes(range=x_range, row=2, col=1)
    # Also update row=1 for explicit consistency
    fig.update_xaxes(range=x_range, row=1, col=1)


def update_colorscale(fig: go.Figure, colorscale: str) -> None:  # pragma: no cover
    """Update the colorscale for the heatmap in an image/line plotly figure."""
    colorscale_value = get_colorscale(colorscale)
    fig.update_traces(
        colorscale=colorscale_value,
        selector=dict(type="heatmap"),
    )


def update_contrast(  # pragma: no cover
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


# DEPRECATED: This function is no longer used. Use dict-based updates instead:
# - update_xaxis_range_v2(plotly_dict, x_range) for x-axis
# - update_yaxis_range_v2(plotly_dict, y_range, row=1) for y-axis
# See ImageLineViewerView._reset_zoom() for example usage.
# def reset_image_zoom(fig: go.Figure, kf: Optional[KymImage]) -> None:  # pragma: no cover
#     """Reset the zoom to full scale for the kymograph image subplot."""
#     if kf is None:
#         return
#
#     duration_seconds = None
#     if kf.header.physical_size and len(kf.header.physical_size) > 0:
#         duration_seconds = kf.header.physical_size[0]
#     if duration_seconds is None:
#         return
#     pixels_per_line = kf.pixels_per_line
#
#     # logger.info(f"reset_image_zoom: duration_seconds: {duration_seconds} pixels_per_line: {pixels_per_line}")
#
#     # Reset x-axis (time) for both subplots (they're shared)
#     fig.update_xaxes(range=[0, duration_seconds], row=1, col=1)
#     fig.update_xaxes(range=[0, duration_seconds], row=2, col=1)
#
#     # Reset y-axis (position) for image subplot only
#     fig.update_yaxes(range=[0, pixels_per_line - 1], row=1, col=1)
