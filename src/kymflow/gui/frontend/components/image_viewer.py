from __future__ import annotations

import plotly.graph_objects as go
from nicegui import ui

from kymflow.core.plotting.theme import ThemeMode
from kymflow.core.plotting import image_plot_plotly
from kymflow.gui.state import AppState

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def create_image_viewer(app_state: AppState) -> None:
    plot = ui.plotly(go.Figure()).classes("w-full h-64")
    state = {
        "image": None,
        "theme": app_state.theme_mode,
    }

    def _render_current() -> None:
        image = state["image"]
        theme = state["theme"]
        fig = image_plot_plotly(image, theme)
        plot.update_figure(fig)

    def _on_selection(kf, origin) -> None:
        if not kf:
            state["image"] = None
            plot.update_figure(go.Figure())
            return
        logger.info("Selection changed, loading image")
        image = kf.get_img_slice(channel=1)
        state["image"] = image
        _render_current()

    def _on_theme_change(mode: ThemeMode) -> None:
        state["theme"] = mode
        if state["image"] is None:
            return
        _render_current()
    
    # Register callbacks (no decorators - explicit registration)
    app_state.on_selection_changed(_on_selection)
    app_state.on_theme_changed(_on_theme_change)
