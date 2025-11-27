from __future__ import annotations

import plotly.graph_objects as go
from nicegui import ui

import numpy as np

from kymflow_core.enums import ThemeMode
from kymflow_core.kym_file import _medianFilter, _removeOutliers
from kymflow_core.plotting import (
    plot_image_line_plotly,
    update_colorscale,
    update_contrast,
    reset_image_zoom,
)
from kymflow_core.state import AppState, ImageDisplayParams

from kymflow_core.utils.logging import get_logger

logger = get_logger(__name__)


def create_image_line_viewer(app_state: AppState) -> None:
    """Create a combined viewer showing kymograph image and velocity plot in subplots."""
    # Filter checkboxes and zoom button
    with ui.row().classes("w-full gap-2 items-center"):
        remove_outliers_cb = ui.checkbox("Remove outliers")
        median_filter_cb = ui.checkbox("Median filter")
        full_zoom_btn = ui.button("Full zoom", icon="zoom_out_map")
    
    # Plot with larger height to accommodate both subplots
    plot = ui.plotly(go.Figure()).classes("w-full")
    state = {
        "selected": None,
        "theme": app_state.theme_mode,
        "display_params": None,  # Store ImageDisplayParams
        "current_figure": None,  # Store current figure reference for partial updates
        "original_y_values": None,  # Store original unfiltered y-values for line plot
        "original_time_values": None,  # Store original time values for line plot
        "uirevision": 0,  # Counter to control Plotly's uirevision for forced resets
    }

    def _set_uirevision(fig: go.Figure) -> None:
        """Apply the current uirevision to the figure."""
        fig.layout.uirevision = f"kymflow-plot-{state['uirevision']}"

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
        
        # Store original unfiltered y-values for partial updates
        if kf is not None:
            time_values = kf.getAnalysisValue("time")
            y_values = kf.getAnalysisValue("velocity")
            if time_values is not None and y_values is not None:
                state["original_time_values"] = np.array(time_values).copy()
                state["original_y_values"] = np.array(y_values).copy()
            else:
                state["original_time_values"] = None
                state["original_y_values"] = None
        else:
            state["original_time_values"] = None
            state["original_y_values"] = None
        
        # Store figure reference
        _set_uirevision(fig)
        state["current_figure"] = fig
        plot.update_figure(fig)

    def _reset_zoom(force_new_uirevision: bool = False) -> None:
        """Reset zoom while optionally forcing Plotly to drop preserved UI state."""
        fig = state["current_figure"]
        kf = state["selected"]
        if fig is None or kf is None:
            return

        if force_new_uirevision:
            state["uirevision"] += 1
            _set_uirevision(fig)

        reset_image_zoom(fig, kf)
        plot.update_figure(fig)

    @app_state.selection_changed.connect
    def _on_selection(kf, origin) -> None:
        state["selected"] = kf
        _render_combined()
        # Reset to full zoom when selection changes
        _reset_zoom(force_new_uirevision=True)

    @app_state.metadata_changed.connect
    def _on_metadata(kf) -> None:
        if kf is app_state.selected_file:
            _render_combined()

    def _update_line_plot_partial() -> None:
        """Update only the Scatter trace y-values when filters change, preserving zoom."""
        fig = state["current_figure"]
        if fig is None:
            # No figure yet, do full render
            _render_combined()
            return
        
        original_y = state["original_y_values"]
        if original_y is None:
            # No data available, do full render
            _render_combined()
            return
        
        # Get current filter settings
        remove_outliers = remove_outliers_cb.value
        median_filter_size = 5 if median_filter_cb.value else 0
        
        # Re-compute filtered y-values
        filtered_y = original_y.copy()
        if remove_outliers:
            filtered_y = _removeOutliers(filtered_y)
        if median_filter_size > 0:
            if median_filter_size % 2 == 0:
                median_filter_size = 5  # Default to 5 if even
            filtered_y = _medianFilter(filtered_y, median_filter_size)
        
        # Find the Scatter trace and update its y-values
        for trace in fig.data:
            if isinstance(trace, go.Scatter):
                trace.y = filtered_y
                break
        else:
            # No Scatter trace found, do full render
            _render_combined()
            return
        
        # Update the plot with modified figure (preserves zoom via uirevision)
        plot.update_figure(fig)
    
    def _on_filter_change() -> None:
        """Handle filter checkbox changes - use partial update to preserve zoom."""
        _update_line_plot_partial()

    @app_state.theme_changed.connect
    def _on_theme_change(mode: ThemeMode) -> None:
        """Handle theme change - requires full render."""
        state["theme"] = mode
        _render_combined()

    def _update_contrast_partial() -> None:
        """Update only colorscale/zmin/zmax when contrast changes, preserving zoom."""
        fig = state["current_figure"]
        if fig is None:
            # No figure yet, ignore contrast changes
            return
        
        display_params = state["display_params"]
        if display_params is None:
            return
        
        # Update colorscale
        update_colorscale(fig, display_params.colorscale)
        
        # Update contrast (zmin/zmax)
        update_contrast(fig, zmin=display_params.zmin, zmax=display_params.zmax)
        
        # Update the plot with modified figure (preserves zoom via uirevision)
        plot.update_figure(fig)

    @app_state.image_display_changed.connect
    def _on_image_display_change(params: ImageDisplayParams) -> None:
        """Handle image display parameter changes from contrast widget.
        
        Uses partial updates to preserve zoom/pan state.
        """
        state["display_params"] = params
        _update_contrast_partial()

    def _on_full_zoom() -> None:
        """Handle full zoom button click - reset image zoom to full scale."""
        _reset_zoom(force_new_uirevision=True)

    remove_outliers_cb.on("update:model-value", _on_filter_change)
    median_filter_cb.on("update:model-value", _on_filter_change)
    full_zoom_btn.on("click", _on_full_zoom)
