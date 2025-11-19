from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from nicegui import ui

from kymflow_core.state import AppState

from kymflow_core.utils.logging import get_logger
logger = get_logger(__name__)

def _figure_from_image(image: np.ndarray) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=image.T,
            colorscale="Gray",
            showscale=False,
        )
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(showticklabels=False),
        yaxis=dict(showticklabels=False),
    )
    return fig


def create_image_viewer(app_state: AppState) -> None:
    plot = ui.plotly(go.Figure()).classes("w-full h-64")

    @app_state.selection_changed.connect
    def _on_selection(kf, origin) -> None:
        if not kf:
            plot.update_figure(go.Figure())
            return
        logger.info('Selection changed, loading image')
        image = kf.ensure_image_loaded()
        plot.update_figure(_figure_from_image(image))
