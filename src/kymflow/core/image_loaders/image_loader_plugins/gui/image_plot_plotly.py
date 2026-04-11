"""Minimal Plotly heatmap for 2D image preview (folder catalog demo only).

Duplicated from :func:`kymflow.core.plotting.image_plots.image_plot_plotly` behavior
without importing ``kymflow.core.plotting`` so ``image_loader_plugins`` stays self-contained.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import plotly.graph_objects as go

from kymflow.core.image_loaders.image_loader_plugins.my_image_import import ImageHeader


def image_plot_plotly(
    image: Optional[np.ndarray],
    *,
    header: Optional[ImageHeader] = None,
) -> go.Figure:
    """Create a grayscale heatmap from a 2D array, or an empty figure if ``image`` is None.

    When ``header`` is given and ``image`` is 2D with shape ``(Y, X)``, uniform axes come
    from :meth:`~ImageHeader.plotly_heatmap_uniform_axes_for_transpose_z` (see that method
    for the ``z = image.transpose()`` convention).
    """
    bg_color = "white"
    template = "plotly_white"

    if image is None:
        fig = go.Figure()
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
        )
        return fig

    fig = go.Figure()
    if header is not None and image.ndim == 2:
        ax = header.plotly_heatmap_uniform_axes_for_transpose_z(
            (image.shape[0], image.shape[1])
        )
        fig.add_trace(
            go.Heatmap(
                x0=ax.x0,
                dx=ax.dx,
                y0=ax.y0,
                dy=ax.dy,
                z=image.transpose(),
                xtype="scaled",
                ytype="scaled",
                colorscale="Gray",
                showscale=False,
            )
        )
        # Do not set xaxis/yaxis ``range`` here: fixed ranges fight Plotly's heatmap
        # autorange (including y direction) and broke axis alignment vs the old x/y array path.
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(
                showticklabels=True,
                showgrid=False,
                zeroline=False,
                title=dict(text=ax.x_title),
            ),
            yaxis=dict(
                showticklabels=True,
                showgrid=False,
                zeroline=False,
                title=dict(text=ax.y_title),
            ),
        )
    else:
        fig.add_trace(
            go.Heatmap(
                z=image.transpose(),
                colorscale="Gray",
                showscale=False,
            )
        )
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(showticklabels=True, showgrid=False, zeroline=False),
            yaxis=dict(showticklabels=True, showgrid=False, zeroline=False),
        )
    return fig
