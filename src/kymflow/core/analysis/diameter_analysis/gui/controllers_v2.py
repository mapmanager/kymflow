"""AppControllerV2: drives ImageRoiWidget and LinePlotWidget instead of raw plotly dicts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

import numpy as np

from nicewidgets.image_line_widget.models import (
    AxisEvent,
    Channel,
    ChannelManager,
    LineConfig,
    RegionOfInterest,
)

from .controllers import AppController
from .models import AppState
from .plotting import (
    _extract_diameter_um,
    _extract_filtered_diameter_um,
    _extract_time_s,
    apply_post_filter_1d,
)

if TYPE_CHECKING:
    from nicewidgets.image_line_widget.image_roi_widget import ImageRoiWidget
    from nicewidgets.image_line_widget.line_plot_widget import LinePlotWidget


class AppControllerV2(AppController):
    """Controller that owns ImageRoiWidget and LinePlotWidget; populates them via widget APIs."""

    def __init__(
        self,
        state: AppState,
        *,
        on_state_change: Optional[Any] = None,
    ) -> None:
        super().__init__(state, on_state_change=on_state_change)
        self._image_roi_widget: Optional[ImageRoiWidget] = None
        self._line_plot_widget: Optional[LinePlotWidget] = None
        self._syncing_axes = False

    def register_widgets(
        self,
        image_roi_widget: ImageRoiWidget,
        line_plot_widget: LinePlotWidget,
    ) -> None:
        self._image_roi_widget = image_roi_widget
        self._line_plot_widget = line_plot_widget
        self._populate_widgets()

    def _state_to_channel_manager(self) -> ChannelManager:
        """Build ChannelManager from current state. Uses placeholder when no image."""
        if self.state.img is None:
            # Placeholder for initial no-image case
            placeholder = np.zeros((10, 10), dtype=np.float64)
            return ChannelManager(
                channels=[Channel("Kymograph", placeholder)],
                row_scale=1.0,
                col_scale=1.0,
                x_label="time (s)",
                y_label="space (um)",
            )
        seconds_per_line, um_per_pixel = self.resolve_units(source=self.state.source)
        return ChannelManager(
            channels=[Channel("Kymograph", self.state.img)],
            row_scale=float(seconds_per_line),
            col_scale=float(um_per_pixel),
            x_label="time (s)",
            y_label="space (um)",
        )

    def _full_extent_roi(self) -> RegionOfInterest:
        """Build full-extent ROI for current image. Uses (0,0,9,9) when no image."""
        if self.state.img is None:
            return RegionOfInterest("Full", 0, 9, 0, 9)
        n_time, n_space = self.state.img.shape
        return RegionOfInterest("Full", 0, max(0, n_time - 1), 0, max(0, n_space - 1))

    def on_axis_change(self, ev: AxisEvent) -> None:
        """Sync x-axis between kymograph and diameter widgets."""
        if self._syncing_axes:
            return
        img_w = self._image_roi_widget
        line_w = self._line_plot_widget
        if img_w is None or line_w is None:
            return

        self._syncing_axes = True
        try:
            if ev.widget_name == "kymograph":
                if ev.x_range is None:
                    line_w.set_x_axis_autorange()
                else:
                    line_w.set_x_axis_range(ev.x_range)
            elif ev.widget_name == "diameter":
                if ev.x_range is None:
                    img_w.set_x_axis_autorange()
                else:
                    img_w.set_x_axis_range(ev.x_range)
        finally:
            self._syncing_axes = False

    def _populate_widgets(self) -> None:
        """Push current state to ImageRoiWidget and LinePlotWidget."""
        img_w = self._image_roi_widget
        line_w = self._line_plot_widget
        if img_w is None or line_w is None:
            return

        manager = self._state_to_channel_manager()
        roi = self._full_extent_roi()

        img_w.set_file(manager, [roi])

        # Edge overlays on kymograph
        img_w.clear_lines()
        if self.state.img is not None:
            try:
                seconds, left_um, right_um, center_um = self._extract_overlays_um()
                if not self.state.gui.show_center_overlay:
                    center_um = None
                line_cfg = LineConfig(line_width=4)
                if left_um is not None:
                    img_w.add_line(seconds, left_um, "left", config=line_cfg)
                if right_um is not None:
                    img_w.add_line(seconds, right_um, "right", config=line_cfg)
                if center_um is not None:
                    img_w.add_line(seconds, center_um, "center", config=line_cfg)
            except RuntimeError:
                pass

        # Diameter trace on line plot
        line_w.clear_lines()
        res = self.state.results
        if res is not None and self.state.img is not None:
            seconds_per_line, um_per_pixel = self.resolve_units(source=self.state.source)
            d_um = _extract_diameter_um(res, float(um_per_pixel))
            if d_um is not None:
                t = _extract_time_s(res, float(seconds_per_line), len(d_um))
                line_w.add_line(
                    t,
                    d_um,
                    "Diameter",
                    x_label="time (s)",
                    y_label="diameter (um)",
                )
                if self.state.post_filter_params and bool(
                    getattr(self.state.post_filter_params, "enabled", False)
                ):
                    d_f = _extract_filtered_diameter_um(res)
                    if d_f is None:
                        d_f = apply_post_filter_1d(d_um, self.state.post_filter_params)
                    line_w.add_line(
                        t,
                        d_f,
                        "Diameter filtered",
                        config=LineConfig(line_width=2, line_color="gray"),
                    )

    def _rebuild_figures(self) -> None:
        """Override: update widgets instead of fig_img/fig_line."""
        self._populate_widgets()
