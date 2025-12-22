"""Contrast adjustment widget for image display controls."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from nicegui import ui

from kymflow.gui.events import ImageDisplayOrigin
from kymflow.core.plotting.theme import ThemeMode
from kymflow.core.plotting.colorscales import COLORSCALE_OPTIONS
from kymflow.core.plotting.image_plots import histogram_plot_plotly
from kymflow.gui.state import AppState, ImageDisplayParams

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def create_contrast_widget(app_state: AppState) -> None:
    """Create contrast adjustment widget with color LUT, sliders, and histogram.

    Layout:
    - Row 1: Color LUT dropdown and Log scale checkbox
    - Row 2: Histogram plot
    - Row 3: Min slider (aligned with histogram x-axis)
    - Row 4: Max slider (aligned with histogram x-axis)
    """
    # Initialize state
    state = {
        "current_image": None,
        "colorscale": "Gray",
        "zmin": 0,
        "zmax": 255,
        "log_histogram": True,
        "theme": app_state.theme_mode,
        "updating_programmatically": False,  # Flag to prevent feedback loops
    }

    # Row 1: Color LUT dropdown and Log scale checkbox
    with ui.row().classes("w-full gap-4 items-center"):
        colorscale_options = [opt["value"] for opt in COLORSCALE_OPTIONS]

        colorscale_select = ui.select(
            colorscale_options,
            value="Gray",
            label="Color LUT",
        ).classes("flex-1")

        log_checkbox = ui.checkbox("Log", value=True)

    # Row 2: Histogram plot
    histogram_plot = ui.plotly(go.Figure()).classes("w-full h-48")

    # Row 3: Min slider
    with ui.row().classes("w-full items-center gap-2"):
        # with ui.row().classes("w-full"):
        ui.label("Min:").classes("w-12")
        # min_value_label = ui.label("0").classes("w-16")
        min_slider = ui.slider(
            min=0,
            max=255,
            value=0,
            step=1,
            # ).classes("flex-1")
        ).classes("flex-1")
        min_value_label = ui.label("0").classes("w-16")

    # Row 4: Max slider
    with ui.row().classes("w-full items-center gap-2"):
        ui.label("Max:").classes("w-12")
        max_slider = ui.slider(
            min=0,
            max=255,
            value=255,
            step=1,
        ).classes("flex-1")
        max_value_label = ui.label("255").classes("w-16")

    def _update_histogram() -> None:
        """Update histogram plot with current settings."""
        image = state["current_image"]
        zmin = state["zmin"]
        zmax = state["zmax"]
        log_scale = state["log_histogram"]
        theme = state["theme"]

        fig = histogram_plot_plotly(
            image=image,
            zmin=zmin,
            zmax=zmax,
            log_scale=log_scale,
            theme=theme,
        )
        histogram_plot.update_figure(fig)

    def _on_colorscale_change(e) -> None:
        """Handle colorscale change."""
        state["colorscale"] = (
            e.value if hasattr(e, "value") else colorscale_select.value
        )
        params = ImageDisplayParams(
            colorscale=state["colorscale"],
            zmin=state["zmin"],
            zmax=state["zmax"],
            origin=ImageDisplayOrigin.CONTRAST_WIDGET,
        )
        app_state.set_image_display(params)

    def _on_slider_change() -> None:
        """Handle slider change (min or max)."""
        # Skip if we're updating programmatically to prevent feedback loop
        if state["updating_programmatically"]:
            return

        new_zmin = int(min_slider.value)
        new_zmax = int(max_slider.value)

        # Ensure zmin <= zmax
        if new_zmin > new_zmax:
            state["updating_programmatically"] = True
            try:
                if min_slider.value == new_zmin:
                    # Min slider moved past max, adjust max
                    new_zmax = new_zmin
                    max_slider.value = new_zmax
                    max_value_label.text = str(new_zmax)
                else:
                    # Max slider moved below min, adjust min
                    new_zmin = new_zmax
                    min_slider.value = new_zmin
                    min_value_label.text = str(new_zmin)
            finally:
                state["updating_programmatically"] = False

        state["zmin"] = new_zmin
        state["zmax"] = new_zmax

        # Update labels immediately for user feedback
        min_value_label.text = str(new_zmin)
        max_value_label.text = str(new_zmax)

        # Emit signal and update histogram (these are throttled via event handler)
        params = ImageDisplayParams(
            colorscale=state["colorscale"],
            zmin=state["zmin"],
            zmax=state["zmax"],
            origin=ImageDisplayOrigin.CONTRAST_WIDGET,
        )
        app_state.set_image_display(params)
        _update_histogram()

    def _on_log_toggle() -> None:
        """Handle log scale checkbox toggle."""
        state["log_histogram"] = log_checkbox.value
        _update_histogram()

    def _on_selection_change(kf, origin) -> None:
        """Handle file selection change."""
        # Set flag to prevent slider change handlers from firing
        state["updating_programmatically"] = True
        try:
            if kf is None:
                state["current_image"] = None
                state["zmin"] = 0
                state["zmax"] = 255
                min_slider.value = 0
                max_slider.value = 255
                min_slider.props("max=255")
                max_slider.props("max=255")
                min_value_label.text = "0"
                max_value_label.text = "255"
                _update_histogram()
                return

            # Load image
            image = kf.get_img_slice(channel=1)
            state["current_image"] = image

            if image is not None:
                # Calculate max value
                image_max = int(np.max(image))

                # Reset sliders
                state["zmin"] = 0
                state["zmax"] = image_max

                # Update slider ranges and values
                min_slider.props(f"max={image_max}")
                max_slider.props(f"max={image_max}")
                min_slider.value = 0
                max_slider.value = image_max
                min_value_label.text = "0"
                max_value_label.text = str(image_max)

                # Update histogram and emit signal
                _update_histogram()
                params = ImageDisplayParams(
                    colorscale=state["colorscale"],
                    zmin=state["zmin"],
                    zmax=state["zmax"],
                    origin=ImageDisplayOrigin.PROGRAMMATIC,
                )
                app_state.set_image_display(params)
            else:
                # No image available
                state["zmin"] = 0
                state["zmax"] = 255
                min_slider.value = 0
                max_slider.value = 255
                min_value_label.text = "0"
                max_value_label.text = "255"
                _update_histogram()
        finally:
            state["updating_programmatically"] = False

    def _on_theme_change(mode: ThemeMode) -> None:
        """Handle theme change."""
        state["theme"] = mode
        _update_histogram()
    
    # Register callbacks (no decorators - explicit registration)
    app_state.on_selection_changed(_on_selection_change)
    app_state.on_theme_changed(_on_theme_change)
    
    # Connect UI element handlers (these are safe - tied to element lifecycle)
    colorscale_select.on("update:model-value", _on_colorscale_change)
    # Throttle slider events to prevent cascading updates when dragging quickly
    # Use trailing events so we update after user stops dragging
    min_slider.on(
        "update:model-value",
        _on_slider_change,
        throttle=0.2,  # 200ms throttle to batch rapid updates
    )
    max_slider.on(
        "update:model-value",
        _on_slider_change,
        throttle=0.2,  # 200ms throttle to batch rapid updates
    )
    log_checkbox.on("update:model-value", _on_log_toggle)

    # Initialize with current selection
    if app_state.selected_file:
        _on_selection_change(app_state.selected_file, None)
