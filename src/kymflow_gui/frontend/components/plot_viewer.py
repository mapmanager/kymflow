from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from nicegui import ui

from kymflow_core.state import AppState


def create_plot_viewer(app_state: AppState) -> None:
    plot = ui.plotly(go.Figure()).classes("w-full h-52")

    def _update_for_file(kf) -> None:
        if not kf:
            plot.update_figure(go.Figure())
            return
        payload = kf.get_analysis_payload_or_load()
        if not payload:
            fig = go.Figure()
            fig.add_annotation(
                text="Run analysis to see velocity trace",
                showarrow=False,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
            )
            plot.update_figure(fig)
            return
        header = kf.ensure_header_loaded()
        seconds_per_line = header.seconds_per_line or 1.0
        um_per_pixel = header.um_per_pixel or 1.0

        time_axis = payload["time_indices"] * seconds_per_line
        theta = np.deg2rad(payload["theta_degrees"])
        velocity = (um_per_pixel / seconds_per_line) * np.tan(theta) / 1000.0

        fig = go.Figure(
            go.Scatter(
                x=time_axis,
                y=velocity,
                mode="lines",
            )
        )
        fig.update_layout(
            xaxis_title="Time (s)",
            yaxis_title="Velocity (mm/s)",
            margin=dict(l=50, r=10, t=10, b=40),
        )
        plot.update_figure(fig)

    @app_state.selection_changed.connect
    def _on_selection(kf, origin) -> None:
        _update_for_file(kf)

    @app_state.metadata_changed.connect
    def _on_metadata(kf) -> None:
        if kf is app_state.selected_file:
            _update_for_file(kf)
