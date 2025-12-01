from __future__ import annotations

import plotly.graph_objects as go
from nicegui import ui

from kymflow.core.enums import ThemeMode
from kymflow.core.plotting import image_plot_plotly
from kymflow.core.state import AppState

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
