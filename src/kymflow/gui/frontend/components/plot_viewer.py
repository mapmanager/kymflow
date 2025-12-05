from __future__ import annotations

import plotly.graph_objects as go
from nicegui import ui

from kymflow.core.plotting.theme import ThemeMode
from kymflow.core.plotting import line_plot_plotly
from kymflow.gui.state import AppState


def create_plot_viewer(app_state: AppState) -> None:
    # Filter checkboxes
    with ui.row().classes("w-full gap-2 items-center"):
        remove_outliers_cb = ui.checkbox("Remove outliers")
        median_filter_cb = ui.checkbox("Median filter")

    plot = ui.plotly(go.Figure()).classes("w-full h-52")
    state = {
        "selected": None,
        "theme": app_state.theme_mode,
    }

    def _render_plot() -> None:
        kf = state["selected"]
        theme = state["theme"]

        # Convert checkbox to median_filter int (0 = off, 5 = on with window size 5)
        median_filter_size = 5 if median_filter_cb.value else 0

        fig = line_plot_plotly(
            kf=kf,
            x="time",
            y="velocity",
            remove_outliers=remove_outliers_cb.value,
            median_filter=median_filter_size,
            theme=theme,
        )
        plot.update_figure(fig)

    def _on_selection(kf, origin) -> None:
        state["selected"] = kf
        _render_plot()

    def _on_metadata(kf) -> None:
        if kf is app_state.selected_file:
            _render_plot()

    def _on_filter_change() -> None:
        _render_plot()

    def _on_theme_change(mode: ThemeMode) -> None:
        state["theme"] = mode
        _render_plot()
    
    # Register callbacks (no decorators - explicit registration)
    app_state.on_selection_changed(_on_selection)
    app_state.on_metadata_changed(_on_metadata)
    app_state.on_theme_changed(_on_theme_change)
    
    remove_outliers_cb.on("update:model-value", _on_filter_change)
    median_filter_cb.on("update:model-value", _on_filter_change)
