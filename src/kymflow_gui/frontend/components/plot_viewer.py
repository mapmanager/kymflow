from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from nicegui import ui

from kymflow_core.enums import ThemeMode
from kymflow_core.kym_file import _medianFilter, _removeOutliers
from kymflow_core.state import AppState


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

    def _build_template_colors(theme: ThemeMode) -> tuple[str, str]:
        bg = "#000000" if theme is ThemeMode.DARK else "#ffffff"
        fg = "#ffffff" if theme is ThemeMode.DARK else "#000000"
        return bg, fg

    def _render_plot() -> None:
        kf = state["selected"]
        theme = state["theme"]
        template = "plotly_dark" if theme is ThemeMode.DARK else "plotly_white"
        bg_color, fg_color = _build_template_colors(theme)

        if not kf:
            fig = go.Figure()
            fig.update_layout(
                template=template,
                paper_bgcolor=bg_color,
                plot_bgcolor=bg_color,
            )
            plot.update_figure(fig)
            return

        time_values = kf.getAnalysisValue("time")
        velocity_values = kf.getAnalysisValue("velocity")

        if time_values is None or velocity_values is None:
            fig = go.Figure()
            fig.add_annotation(
                text="Run analysis to see velocity trace",
                showarrow=False,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                font=dict(color=fg_color),
            )
            fig.update_layout(
                template=template,
                paper_bgcolor=bg_color,
                plot_bgcolor=bg_color,
            )
            plot.update_figure(fig)
            return

        filtered_velocity = (
            velocity_values.copy()
            if isinstance(velocity_values, np.ndarray)
            else np.array(velocity_values)
        )

        if remove_outliers_cb.value:
            filtered_velocity = _removeOutliers(filtered_velocity)

        if median_filter_cb.value:
            filtered_velocity = _medianFilter(filtered_velocity)

        fig = go.Figure(
            go.Scatter(
                x=time_values,
                y=filtered_velocity,
                mode="lines",
            )
        )
        fig.update_layout(
            template=template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font=dict(color=fg_color),
            xaxis=dict(
                title="Time (s)",
                color=fg_color,
                gridcolor="rgba(255,255,255,0.2)" if theme is ThemeMode.DARK else "#cccccc",
            ),
            yaxis=dict(
                title="Velocity (mm/s)",
                color=fg_color,
                gridcolor="rgba(255,255,255,0.2)" if theme is ThemeMode.DARK else "#cccccc",
            ),
            margin=dict(l=50, r=10, t=10, b=40),
        )
        plot.update_figure(fig)

    @app_state.selection_changed.connect
    def _on_selection(kf, origin) -> None:
        state["selected"] = kf
        _render_plot()

    @app_state.metadata_changed.connect
    def _on_metadata(kf) -> None:
        if kf is app_state.selected_file:
            _render_plot()

    def _on_filter_change() -> None:
        _render_plot()

    @app_state.theme_changed.connect
    def _on_theme_change(mode: ThemeMode) -> None:
        state["theme"] = mode
        _render_plot()

    remove_outliers_cb.on("update:model-value", _on_filter_change)
    median_filter_cb.on("update:model-value", _on_filter_change)
