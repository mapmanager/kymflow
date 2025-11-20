from __future__ import annotations

from typing import Optional

import numpy as np
import plotly.graph_objects as go

from kymflow_core.enums import ThemeMode

from .theme import get_theme_colors, get_theme_template


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

