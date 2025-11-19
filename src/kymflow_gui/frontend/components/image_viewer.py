from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from nicegui import ui

from kymflow_core.enums import ThemeMode
from kymflow_core.state import AppState

from kymflow_core.utils.logging import get_logger

logger = get_logger(__name__)


def _figure_from_image(image: np.ndarray, theme: ThemeMode) -> go.Figure:
    template = "plotly_dark" if theme is ThemeMode.DARK else "plotly_white"
    bg_color = "#000000" if theme is ThemeMode.DARK else "#ffffff"
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


def create_image_viewer(app_state: AppState) -> None:
    plot = ui.plotly(go.Figure()).classes("w-full h-64")
    state = {
        "image": None,
        "theme": app_state.theme_mode,
    }

    def _render_current() -> None:
        image = state["image"]
        if image is None:
            plot.update_figure(go.Figure())
            return
        plot.update_figure(_figure_from_image(image, state["theme"]))

    @app_state.selection_changed.connect
    def _on_selection(kf, origin) -> None:
        if not kf:
            state["image"] = None
            plot.update_figure(go.Figure())
            return
        logger.info("Selection changed, loading image")
        image = kf.ensure_image_loaded()
        state["image"] = image
        _render_current()

    @app_state.theme_changed.connect
    def _on_theme_change(mode: ThemeMode) -> None:
        state["theme"] = mode
        if state["image"] is None:
            return
        _render_current()
