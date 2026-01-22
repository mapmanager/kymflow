"""Contrast adjustment view component.

This module provides a view component that displays contrast controls (colorscale,
sliders, histogram) for adjusting image display parameters. The view emits
ImageDisplayChange(phase="intent") events when users adjust controls, but does not
subscribe to events (that's handled by ContrastBindings).
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
import plotly.graph_objects as go
from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.plotting.colorscales import COLORSCALE_OPTIONS
from kymflow.core.plotting.image_plots import histogram_plot_plotly
from kymflow.core.plotting.theme import ThemeMode
from kymflow.gui_v2.events_legacy import ImageDisplayOrigin
from kymflow.gui_v2.state import ImageDisplayParams
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import ImageDisplayChange, SelectionOrigin
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

OnImageDisplayChange = Callable[[ImageDisplayChange], None]


class ContrastView:
    """Contrast adjustment view component.

    This view displays contrast controls with color LUT dropdown, histogram plot,
    and min/max sliders. Users can adjust these controls, which triggers
    ImageDisplayChange(phase="intent") events.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by bindings)
        - Events emitted via on_image_display_change callback

    Attributes:
        _on_image_display_change: Callback function that receives ImageDisplayChange events.
        _colorscale_select: Color LUT dropdown (created in render()).
        _log_checkbox: Log scale checkbox (created in render()).
        _histogram_plot: Histogram plot component (created in render()).
        _min_slider: Min value slider (created in render()).
        _max_slider: Max value slider (created in render()).
        _min_value_label: Min value label (created in render()).
        _max_value_label: Max value label (created in render()).
        _current_file: Currently selected file (for histogram).
        _current_image: Current image data (for histogram).
        _theme: Current theme mode.
        _display_params: Current image display parameters.
        _updating_programmatically: Flag to prevent feedback loops.
    """

    def __init__(self, *, on_image_display_change: OnImageDisplayChange) -> None:
        """Initialize contrast view.

        Args:
            on_image_display_change: Callback function that receives ImageDisplayChange events.
        """
        self._on_image_display_change = on_image_display_change

        # UI components (created in render())
        self._colorscale_select: Optional[ui.select] = None
        self._log_checkbox: Optional[ui.checkbox] = None
        self._histogram_plot: Optional[ui.plotly] = None
        self._min_slider: Optional[ui.slider] = None
        self._max_slider: Optional[ui.slider] = None
        self._min_value_label: Optional[ui.label] = None
        self._max_value_label: Optional[ui.label] = None

        # State
        self._current_file: Optional[KymImage] = None
        self._current_image: Optional[np.ndarray] = None
        self._theme: ThemeMode = ThemeMode.DARK
        self._display_params: Optional[ImageDisplayParams] = None
        self._updating_programmatically: bool = False

    def render(self) -> None:
        """Create the contrast controls UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.
        """
        # Always reset UI element references
        self._colorscale_select = None
        self._log_checkbox = None
        self._histogram_plot = None
        self._min_slider = None
        self._max_slider = None
        self._min_value_label = None
        self._max_value_label = None
        self._updating_programmatically = False

        # Row 1: Color LUT dropdown and Log scale checkbox
        with ui.row().classes("w-full gap-4 items-center"):
            colorscale_options = [opt["value"] for opt in COLORSCALE_OPTIONS]
            self._colorscale_select = ui.select(
                colorscale_options,
                value="Gray",
                label="Color LUT",
            ).classes("flex-1")
            self._colorscale_select.on("update:model-value", self._on_colorscale_change)

            self._log_checkbox = ui.checkbox("Log", value=True)
            self._log_checkbox.on("update:model-value", self._on_log_toggle)

        # Row 2: Histogram plot
        self._histogram_plot = ui.plotly(go.Figure()).classes("w-full h-48")

        # Row 3: Min slider
        with ui.row().classes("w-full items-center gap-2"):
            ui.label("Min:").classes("w-12")
            self._min_slider = ui.slider(
                min=0,
                max=255,
                value=0,
                step=1,
            ).classes("flex-1")
            self._min_slider.on(
                "update:model-value",
                self._on_slider_change,
                throttle=0.2,
            )
            self._min_value_label = ui.label("0").classes("w-16")

        # Row 4: Max slider
        with ui.row().classes("w-full items-center gap-2"):
            ui.label("Max:").classes("w-12")
            self._max_slider = ui.slider(
                min=0,
                max=255,
                value=255,
                step=1,
            ).classes("flex-1")
            self._max_slider.on(
                "update:model-value",
                self._on_slider_change,
                throttle=0.2,
            )
            self._max_value_label = ui.label("255").classes("w-16")

    def set_selected_file(self, file: Optional[KymImage]) -> None:
        """Update histogram for new file.

        Called by bindings when FileSelection(phase="state") event is received.
        Updates histogram and resets sliders to image min/max.

        Args:
            file: Selected KymImage instance, or None if selection cleared.
        """
        safe_call(self._set_selected_file_impl, file)

    def _set_selected_file_impl(self, file: Optional[KymImage]) -> None:
        """Internal implementation of set_selected_file."""
        self._current_file = file

        if file is None:
            self._current_image = None
            self._updating_programmatically = True
            try:
                if self._min_slider is not None:
                    self._min_slider.value = 0
                    self._min_slider.props("max=255")
                if self._max_slider is not None:
                    self._max_slider.value = 255
                    self._max_slider.props("max=255")
                if self._min_value_label is not None:
                    self._min_value_label.text = "0"
                if self._max_value_label is not None:
                    self._max_value_label.text = "255"
            finally:
                self._updating_programmatically = False
            self._update_histogram()
            return

        # Load image
        try:
            image = file.get_img_slice(channel=1)
            self._current_image = image
        except Exception as e:
            logger.warning(f"Failed to load image for contrast widget: {e}")
            self._current_image = None
            self._update_histogram()
            return

        if image is not None:
            # Calculate max value
            image_max = int(np.max(image))

            # Reset sliders
            self._updating_programmatically = True
            try:
                if self._min_slider is not None:
                    self._min_slider.props(f"max={image_max}")
                    self._min_slider.value = 0
                if self._max_slider is not None:
                    self._max_slider.props(f"max={image_max}")
                    self._max_slider.value = image_max
                if self._min_value_label is not None:
                    self._min_value_label.text = "0"
                if self._max_value_label is not None:
                    self._max_value_label.text = str(image_max)
            finally:
                self._updating_programmatically = False

            # Update histogram
            self._update_histogram()

            # Don't emit here - let set_image_display handle it when it's called

    def set_image_display(self, params: ImageDisplayParams) -> None:
        """Update sliders/colorscale from state.

        Called by bindings when ImageDisplayChange(phase="state") event is received.
        Updates UI to match current display parameters.

        Args:
            params: ImageDisplayParams containing colorscale, zmin, zmax.
        """
        safe_call(self._set_image_display_impl, params)

    def _set_image_display_impl(self, params: ImageDisplayParams) -> None:
        """Internal implementation of set_image_display."""
        self._display_params = params

        self._updating_programmatically = True
        try:
            # Update colorscale dropdown
            if self._colorscale_select is not None and params.colorscale:
                self._colorscale_select.value = params.colorscale

            # Update sliders
            if params.zmin is not None and self._min_slider is not None:
                self._min_slider.value = params.zmin
                if self._min_value_label is not None:
                    self._min_value_label.text = str(params.zmin)

            if params.zmax is not None and self._max_slider is not None:
                self._max_slider.value = params.zmax
                if self._max_value_label is not None:
                    self._max_value_label.text = str(params.zmax)
        finally:
            self._updating_programmatically = False

        # Update histogram
        self._update_histogram()

    def set_theme(self, theme: ThemeMode) -> None:
        """Update theme.

        Called by bindings when ThemeChanged event is received.
        Updates histogram theme.

        Args:
            theme: New theme mode (DARK or LIGHT).
        """
        safe_call(self._set_theme_impl, theme)

    def _set_theme_impl(self, theme: ThemeMode) -> None:
        """Internal implementation of set_theme."""
        self._theme = theme
        self._update_histogram()

    def _update_histogram(self) -> None:
        """Update histogram plot with current settings."""
        if self._histogram_plot is None:
            return

        image = self._current_image
        zmin = self._display_params.zmin if self._display_params and self._display_params.zmin is not None else 0
        zmax = self._display_params.zmax if self._display_params and self._display_params.zmax is not None else 255
        log_scale = self._log_checkbox.value if self._log_checkbox is not None else True
        theme = self._theme

        fig = histogram_plot_plotly(
            image=image,
            zmin=zmin,
            zmax=zmax,
            log_scale=log_scale,
            theme=theme,
        )
        try:
            self._histogram_plot.update_figure(fig)
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore

    def _on_colorscale_change(self) -> None:
        """Handle colorscale change."""
        if self._updating_programmatically or self._colorscale_select is None:
            return

        colorscale = self._colorscale_select.value
        params = ImageDisplayParams(
            colorscale=colorscale,
            zmin=self._display_params.zmin if self._display_params else None,
            zmax=self._display_params.zmax if self._display_params else None,
            origin=ImageDisplayOrigin.CONTRAST_WIDGET,
        )
        self._emit_intent(params)

    def _on_slider_change(self) -> None:
        """Handle slider change (min or max)."""
        if self._updating_programmatically:
            return

        if self._min_slider is None or self._max_slider is None:
            return

        new_zmin = int(self._min_slider.value)
        new_zmax = int(self._max_slider.value)

        # Ensure zmin <= zmax
        if new_zmin > new_zmax:
            self._updating_programmatically = True
            try:
                if self._min_slider.value == new_zmin:
                    # Min slider moved past max, adjust max
                    new_zmax = new_zmin
                    self._max_slider.value = new_zmax
                    if self._max_value_label is not None:
                        self._max_value_label.text = str(new_zmax)
                else:
                    # Max slider moved below min, adjust min
                    new_zmin = new_zmax
                    self._min_slider.value = new_zmin
                    if self._min_value_label is not None:
                        self._min_value_label.text = str(new_zmin)
            finally:
                self._updating_programmatically = False

        # Update labels immediately for user feedback
        if self._min_value_label is not None:
            self._min_value_label.text = str(new_zmin)
        if self._max_value_label is not None:
            self._max_value_label.text = str(new_zmax)

        # Emit intent event
        params = ImageDisplayParams(
            colorscale=self._display_params.colorscale if self._display_params else "Gray",
            zmin=new_zmin,
            zmax=new_zmax,
            origin=ImageDisplayOrigin.CONTRAST_WIDGET,
        )
        self._emit_intent(params)
        self._update_histogram()

    def _on_log_toggle(self) -> None:
        """Handle log scale checkbox toggle."""
        self._update_histogram()

    def _emit_intent(self, params: ImageDisplayParams) -> None:
        """Emit ImageDisplayChange(phase="intent") event."""
        self._on_image_display_change(
            ImageDisplayChange(
                params=params,
                origin=SelectionOrigin.IMAGE_VIEWER,
                phase="intent",
            )
        )
