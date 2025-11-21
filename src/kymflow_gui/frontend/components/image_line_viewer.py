from __future__ import annotations

import plotly.graph_objects as go
from nicegui import ui

from kymflow_core.enums import ThemeMode
from kymflow_core.plotting import plot_image_line_plotly
from kymflow_core.state import AppState, ImageDisplayParams

from kymflow_core.utils.logging import get_logger

logger = get_logger(__name__)


def create_image_line_viewer(app_state: AppState) -> None:
    """Create a combined viewer showing kymograph image and velocity plot in subplots."""
    # Filter checkboxes (same as plot_viewer)
    with ui.row().classes("w-full gap-2 items-center"):
        remove_outliers_cb = ui.checkbox("Remove outliers")
        median_filter_cb = ui.checkbox("Median filter")
    
    # Plot with larger height to accommodate both subplots
    plot = ui.plotly(go.Figure()).classes("w-full")
    state = {
        "selected": None,
        "theme": app_state.theme_mode,
        "display_params": None,  # Store ImageDisplayParams
    }

    def _render_combined() -> None:
        """Render the combined image and line plot."""
        kf = state["selected"]
        theme = state["theme"]
        display_params = state["display_params"]
        
        # Convert checkbox to median_filter int (0 = off, 5 = on with window size 5)
        median_filter_size = 5 if median_filter_cb.value else 0
        
        # Get display parameters from stored params or use defaults
        colorscale = display_params.colorscale if display_params else "Gray"
        zmin = display_params.zmin if display_params else None
        zmax = display_params.zmax if display_params else None
        
        fig = plot_image_line_plotly(
            kf=kf,
            y="velocity",
            remove_outliers=remove_outliers_cb.value,
            median_filter=median_filter_size,
            theme=theme,
            colorscale=colorscale,
            zmin=zmin,
            zmax=zmax,
        )
        plot.update_figure(fig)

    @app_state.selection_changed.connect
    def _on_selection(kf, origin) -> None:
        state["selected"] = kf
        _render_combined()

    @app_state.metadata_changed.connect
    def _on_metadata(kf) -> None:
        if kf is app_state.selected_file:
            _render_combined()

    def _on_filter_change() -> None:
        _render_combined()

    @app_state.theme_changed.connect
    def _on_theme_change(mode: ThemeMode) -> None:
        state["theme"] = mode
        _render_combined()

    @app_state.image_display_changed.connect
    def _on_image_display_change(params: ImageDisplayParams, origin) -> None:
        """Handle image display parameter changes from contrast widget."""
        state["display_params"] = params
        _render_combined()

    remove_outliers_cb.on("update:model-value", _on_filter_change)
    median_filter_cb.on("update:model-value", _on_filter_change)

