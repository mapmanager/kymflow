from __future__ import annotations

from typing import Optional

import numpy as np
import plotly.graph_objects as go

from kymflow.core.plotting.theme import ThemeMode

from kymflow.core.plotting.theme import get_theme_colors, get_theme_template


def image_plot_plotly(
    image: Optional[np.ndarray],
    theme: Optional[ThemeMode] = None,
) -> go.Figure:
    """Create a heatmap plot from a 2D numpy array (kymograph image).

    Args:
        image: 2D numpy array (kymograph image), or None for empty plot
        theme: Theme mode (DARK or LIGHT). Defaults to LIGHT if None.

    Returns:
        Plotly Figure ready for display
    """
    # Default to LIGHT theme
    if theme is None:
        theme = ThemeMode.LIGHT

    template = get_theme_template(theme)
    bg_color, _ = get_theme_colors(theme)

    # Handle None image
    if image is None:
        fig = go.Figure()
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
        )
        return fig

    # Create heatmap with transposed image
    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=image.T,
            colorscale="Gray",
            showscale=False,
        )
    )
    fig.update_layout(
        template=template,
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
    )
    return fig


def histogram_plot_plotly(
    image: Optional[np.ndarray],
    zmin: Optional[int] = None,
    zmax: Optional[int] = None,
    log_scale: bool = True,
    theme: Optional[ThemeMode] = None,
    bins: int = 256,
) -> go.Figure:
    """Create a histogram plot of image pixel intensities.

    Args:
        image: 2D numpy array (kymograph image), or None for empty plot
        zmin: Minimum intensity value to show as vertical line (optional)
        zmax: Maximum intensity value to show as vertical line (optional)
        log_scale: If True, use log scale for y-axis (default: True)
        theme: Theme mode (DARK or LIGHT). Defaults to LIGHT if None.
        bins: Number of bins for histogram (default: 256)

    Returns:
        Plotly Figure with histogram ready for display
    """
    # Default to LIGHT theme
    if theme is None:
        theme = ThemeMode.LIGHT

    template = get_theme_template(theme)
    bg_color, fg_color = get_theme_colors(theme)
    grid_color = "rgba(255,255,255,0.2)" if theme is ThemeMode.DARK else "#cccccc"

    # Handle None image
    if image is None:
        fig = go.Figure()
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font=dict(color=fg_color),
        )
        return fig

    # Compute histogram of entire image (always full range)
    flat_image = image.flatten()
    hist, bin_edges = np.histogram(flat_image, bins=bins)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    # Get image intensity range for fixed x-axis (always start at 0)
    image_max = float(np.max(flat_image))

    # Create bar chart
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=bin_centers,
            y=hist,
            marker_color=fg_color,
            opacity=0.7,
        )
    )

    # Add vertical lines for zmin and zmax
    if zmin is not None:
        fig.add_vline(
            x=zmin,
            line_dash="dash",
            line_color="blue",
            line_width=2,
            annotation_text="Min",
            annotation_position="top",
        )

    if zmax is not None:
        fig.add_vline(
            x=zmax,
            line_dash="dash",
            line_color="red",
            line_width=2,
            annotation_text="Max",
            annotation_position="top",
        )

    # Configure layout with fixed x-axis range
    fig.update_layout(
        template=template,
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=fg_color),
        xaxis=dict(
            title="Pixel Intensity",
            color=fg_color,
            gridcolor=grid_color,
            range=[0.0, image_max],  # Fix x-axis range: always start at 0, end at max
        ),
        yaxis=dict(
            title="Count",
            color=fg_color,
            gridcolor=grid_color,
            type="log" if log_scale else "linear",
        ),
        # margin=dict(l=50, r=10, t=10, b=40),
        margin=dict(l=0, r=20, t=10, b=20),
        showlegend=False,
    )

    return fig
