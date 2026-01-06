from __future__ import annotations

import plotly.graph_objects as go
from nicegui import ui

import numpy as np
from typing import Optional

from kymflow.core.plotting.theme import ThemeMode
from kymflow.core.plotting import (
    plot_image_line_plotly,
    update_colorscale,
    update_contrast,
    reset_image_zoom,
)
from kymflow.gui.state import AppState, ImageDisplayParams

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def create_image_line_viewer(app_state: AppState) -> None:
    """Create a combined viewer showing kymograph image and velocity plot in subplots."""
    # ROI selector dropdown
    roi_select = ui.select(
        options=[],
        label="ROI",
    ).classes("min-w-32")
    
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

    def _update_roi_dropdown() -> None:
        """Update ROI dropdown options based on current file."""
        kf = state["selected"]
        if kf is None:
            roi_select.options = []
            roi_select.set_value(None)
            return
        
        all_rois = kf.rois.as_list()
        options = [{"label": f"ROI {roi.id}", "value": roi.id} for roi in all_rois]
        roi_select.options = options
        
        # Select first ROI if none selected or current selection is invalid
        roi_ids = kf.rois.get_roi_ids()
        if app_state.selected_roi_id is None or app_state.selected_roi_id not in roi_ids:
            if roi_ids:
                first_roi_id = roi_ids[0]
                app_state.select_roi(first_roi_id)
                roi_select.set_value(first_roi_id)
            else:
                app_state.select_roi(None)
                roi_select.set_value(None)
        else:
            roi_select.set_value(app_state.selected_roi_id)

    def _render_combined() -> None:
        """Render the combined image and line plot."""
        kf = state["selected"]
        theme = state["theme"]
        display_params = state["display_params"]
        roi_id = app_state.selected_roi_id

        # Convert checkbox to median_filter int (0 = off, 5 = on with window size 5)
        median_filter_size = 5 if median_filter_cb.value else 0

        # Get display parameters from stored params or use defaults
        colorscale = display_params.colorscale if display_params else "Gray"
        zmin = display_params.zmin if display_params else None
        zmax = display_params.zmax if display_params else None

        fig = plot_image_line_plotly(
            kf=kf,
            # roi_id=0,  # Dummy value, will result in empty plot
            yStat="velocity",
            remove_outliers=remove_outliers_cb.value,
            median_filter=median_filter_size,
            theme=theme,
            colorscale=colorscale,
            zmin=zmin,
            zmax=zmax,
            selected_roi_id=None,
        )
        # Store original unfiltered y-values for partial updates
        if kf is not None and roi_id is not None:
            kym_analysis = kf.get_kym_analysis()
            if kym_analysis.has_analysis(roi_id):
                time_values = kym_analysis.get_analysis_value(roi_id, "time")
                y_values = kym_analysis.get_analysis_value(roi_id, "velocity")
            else:
                time_values = None
                y_values = None
            if time_values is not None and y_values is not None:
                state["original_time_values"] = np.array(time_values).copy()
                state["original_y_values"] = np.array(y_values).copy()
            else:
                state["original_time_values"] = None
                state["original_y_values"] = None

        # Store figure reference
        _set_uirevision(fig)
        state["current_figure"] = fig
        try:
            plot.update_figure(fig)
        except RuntimeError as e:
            logger.error(f"Error updating figure: {e}")
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore

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
        try:
            plot.update_figure(fig)
        except RuntimeError as e:
            logger.error(f"Error updating figure: {e}")
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore

    def _on_selection(kf, origin) -> None:
        state["selected"] = kf
        _update_roi_dropdown()  # Update dropdown and select first ROI
        _render_combined()
        # Reset to full zoom when selection changes
        _reset_zoom(force_new_uirevision=True)
    
    def _on_roi_selection_change(roi_id: Optional[int]) -> None:
        """Handle ROI selection change from AppState."""
        try:
            if roi_id is not None:
                roi_select.set_value(roi_id)
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore
        _render_combined()
    
    def _on_roi_dropdown_change() -> None:
        """Handle ROI dropdown selection change."""
        roi_id = roi_select.value
        if roi_id is not None:
            app_state.select_roi(roi_id)
        # _render_combined will be called by _on_roi_selection_change

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

        kf = state["selected"]
        roi_id = app_state.selected_roi_id
        
        if kf is None or roi_id is None:
            # No data available, do full render
            _render_combined()
            return

        # Get current filter settings
        remove_outliers = remove_outliers_cb.value
        median_filter_size = 5 if median_filter_cb.value else 0

        # Re-compute filtered y-values using KymAnalysis API
        kym_analysis = kf.get_kym_analysis()
        if not kym_analysis.has_analysis(roi_id):
            # No analysis available, do full render
            _render_combined()
            return
        
        filtered_y = kym_analysis.get_analysis_value(
            roi_id, "velocity", remove_outliers, median_filter_size
        )

        if filtered_y is None:
            # No data available, do full render
            _render_combined()
            return

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
        try:
            plot.update_figure(fig)
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore

    def _on_filter_change() -> None:
        """Handle filter checkbox changes - use partial update to preserve zoom."""
        _update_line_plot_partial()

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
        try:
            plot.update_figure(fig)
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore

    def _on_image_display_change(params: ImageDisplayParams) -> None:
        """Handle image display parameter changes from contrast widget.

        Uses partial updates to preserve zoom/pan state.
        """
        state["display_params"] = params
        _update_contrast_partial()

    def _on_full_zoom() -> None:
        """Handle full zoom button click - reset image zoom to full scale."""
        _reset_zoom(force_new_uirevision=True)
    
    # Register callbacks (no decorators - explicit registration)
    app_state.on_selection_changed(_on_selection)
    app_state.on_metadata_changed(_on_metadata)
    app_state.on_theme_changed(_on_theme_change)
    app_state.on_image_display_changed(_on_image_display_change)
    app_state.on_roi_selection_changed(_on_roi_selection_change)
    
    roi_select.on("update:model-value", _on_roi_dropdown_change)
    remove_outliers_cb.on("update:model-value", _on_filter_change)
    median_filter_cb.on("update:model-value", _on_filter_change)
    full_zoom_btn.on("click", _on_full_zoom)
