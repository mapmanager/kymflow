"""Image/line viewer replacement using nicewidgets ImageRoiWidget and LinePlotWidget.

Phase 2 of the migration plan: composes ImageRoiWidget (kymograph image) and
LinePlotWidget (velocity line + event rects) in a vertical layout.
Phase 3: wired via ImageLineViewerReplacementBindings.
Phase 4: swap into home_page.
Phase 5: drawer filter/zoom wired; apply_filters, reset_zoom, scroll_x, set_event_filter.
Phase 6: ROI edit (ROIEvent UPDATE → EditRoi); recursion fix (suppress ROI select emit when syncing from state).
"""

from __future__ import annotations

from typing import Callable, Literal, Optional

import numpy as np
from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.plotting.theme import ThemeMode as KymflowThemeMode
from kymflow.gui_v2.adapters import (
    kymimage_to_channel_manager,
    velocity_events_to_acq_image_events,
)
from kymflow.gui_v2.state import ImageDisplayParams
from kymflow.gui_v2.events import (
    EditRoi,
    EventSelection,
    SelectionOrigin,
    SetKymEventXRange,
    SetRoiBounds,
)
from kymflow.gui_v2.client_utils import safe_call
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

OnKymEventXRange = Callable[[SetKymEventXRange], None]
OnSetRoiBounds = Callable[[SetRoiBounds], None]
OnRoiSelect = Callable[[int | None], None]
OnEditRoi = Callable[[EditRoi], None]


def _region_of_interest_to_roi_bounds(roi) -> "RoiBounds":
    """Convert nicewidgets RegionOfInterest to kymflow RoiBounds.
    r0,r1=rows=dim0, c0,c1=cols=dim1.
    """
    from kymflow.core.image_loaders.roi import RoiBounds

    return RoiBounds(
        dim0_start=int(min(roi.r0, roi.r1)),
        dim0_stop=int(max(roi.r0, roi.r1)),
        dim1_start=int(min(roi.c0, roi.c1)),
        dim1_stop=int(max(roi.c0, roi.c1)),
    )


def _parse_roi_id_from_name(name: str) -> int | None:
    """Parse roi_id from RegionOfInterest name (e.g. ROI_1 -> 1)."""
    if not name or not name.startswith("ROI_"):
        return None
    try:
        return int(name.split("_", 1)[1])
    except (IndexError, ValueError):
        return None


def _to_nicewidgets_theme(kymflow_theme: KymflowThemeMode) -> str:
    """Map kymflow ThemeMode to nicewidgets-compatible theme string."""
    return "dark" if kymflow_theme is KymflowThemeMode.DARK else "light"


class ImageLineViewerReplacementView:
    """Replacement view composing ImageRoiWidget and LinePlotWidget.

    Implements the same public API as ImageLineViewerView for Phase 4 swap:
    set_selected_file, set_selected_roi, set_theme, set_image_display, render.
    """

    def __init__(
        self,
        *,
        on_kym_event_x_range: OnKymEventXRange | None = None,
        on_set_roi_bounds: OnSetRoiBounds | None = None,
        on_roi_select: OnRoiSelect | None = None,
        on_edit_roi: OnEditRoi | None = None,
    ) -> None:
        self._on_kym_event_x_range = on_kym_event_x_range
        self._on_set_roi_bounds = on_set_roi_bounds
        self._on_roi_select = on_roi_select
        self._on_edit_roi = on_edit_roi

        self._suppress_roi_select_emit = False
        self._container: Optional[ui.element] = None
        self._image_roi_widget = None
        self._line_plot_widget = None

        self._current_file: Optional[KymImage] = None
        self._current_roi_id: Optional[int] = None
        self._theme: KymflowThemeMode = KymflowThemeMode.DARK
        self._display_params: Optional[ImageDisplayParams] = None
        self._remove_outliers: bool = False
        self._median_filter: bool = False
        self._selected_event_id: Optional[str] = None
        self._event_filter: Optional[dict[str, bool]] = None
        self._syncing_axes = False

    def render(self) -> None:
        """Create the viewer UI: ImageRoiWidget + LinePlotWidget in a column."""
        from nicewidgets.image_line_widget.image_roi_widget import ImageRoiWidget
        from nicewidgets.image_line_widget.line_plot_widget import LinePlotWidget
        from nicewidgets.image_line_widget.models import (
            AxisEvent,
            AxisEventType,
            ROIEvent,
            ROIEventType,
        )

        self._container = ui.column().classes("w-full h-full")
        with self._container:
            theme_str = _to_nicewidgets_theme(self._theme)

            def on_roi_event(e: ROIEvent) -> None:
                if e.type is ROIEventType.SELECT and self._on_roi_select and not self._suppress_roi_select_emit:
                    roi_id = _parse_roi_id_from_name(e.roi.name) if e.roi else None
                    self._on_roi_select(roi_id)
                elif e.type is ROIEventType.UPDATE and e.roi and self._on_edit_roi:
                    roi_id = _parse_roi_id_from_name(e.roi.name)
                    if roi_id is not None:
                        bounds = _region_of_interest_to_roi_bounds(e.roi)
                        path = str(self._current_file.path) if self._current_file and hasattr(self._current_file, "path") else None
                        self._on_edit_roi(
                            EditRoi(
                                roi_id=roi_id,
                                bounds=bounds,
                                path=path,
                                origin=SelectionOrigin.IMAGE_VIEWER,
                                phase="intent",
                            )
                        )

            def on_axis_change(ev: AxisEvent) -> None:
                if self._syncing_axes:
                    return
                img_w = self._image_roi_widget
                line_w = self._line_plot_widget
                if img_w is None or line_w is None:
                    return
                self._syncing_axes = True
                try:
                    if ev.widget_name == "image_roi_widget":
                        if ev.x_range is None:
                            line_w.set_x_axis_autorange()
                        else:
                            line_w.set_x_axis_range(ev.x_range)
                    elif ev.widget_name == "line_plot_1":
                        if ev.x_range is None:
                            img_w.set_x_axis_autorange()
                        else:
                            img_w.set_x_axis_range(ev.x_range)
                finally:
                    self._syncing_axes = False

            # Create empty ChannelManager for initial state
            import numpy as np
            from nicewidgets.image_line_widget.models import Channel, ChannelManager, RegionOfInterest

            placeholder = np.zeros((10, 10), dtype=np.float64)
            placeholder_manager = ChannelManager(
                channels=[Channel("Empty", placeholder)],
                row_scale=1.0,
                col_scale=1.0,
                x_label="Time (s)",
                y_label="Space (um)",
            )
            self._image_roi_widget = ImageRoiWidget(
                widget_name="image_roi_widget",
                manager=placeholder_manager,
                initial_rois=[],
                on_roi_event=on_roi_event,
                on_axis_change=on_axis_change,
                theme=theme_str,
            )

            # LinePlotWidget with placeholder data
            x_placeholder = np.arange(10, dtype=float)
            y_placeholder = np.zeros(10)
            self._line_plot_widget = LinePlotWidget(
                widget_name="line_plot_1",
                x=x_placeholder,
                y=y_placeholder,
                name="velocity",
                x_label="Time (s)",
                y_label="Velocity",
                on_axis_change=on_axis_change,
                theme=theme_str,
            )

        # Populate from current state if we have file/roi
        self._refresh_from_state()

    def _refresh_from_state(self) -> None:
        """Update widgets from _current_file and _current_roi_id."""
        if self._image_roi_widget is None or self._line_plot_widget is None:
            return

        kf = self._current_file
        roi_id = self._current_roi_id

        if kf is None:
            # Clear to placeholder
            return

        try:
            manager, rois = kymimage_to_channel_manager(kf)
            theme_str = _to_nicewidgets_theme(self._theme)
            self._image_roi_widget.set_file(manager, rois)
            self._image_roi_widget.set_theme(theme_str)

            if self._display_params:
                self._image_roi_widget.set_colorscale(self._display_params.colorscale)
                if self._display_params.zmin is not None or self._display_params.zmax is not None:
                    self._image_roi_widget.set_contrast(
                        zmin=self._display_params.zmin,
                        zmax=self._display_params.zmax,
                    )

            if roi_id is not None:
                self._suppress_roi_select_emit = True
                try:
                    self._image_roi_widget.select_roi_by_name(f"ROI_{roi_id}")
                finally:
                    self._suppress_roi_select_emit = False

            # Update line plot with velocity + events
            kym_analysis = kf.get_kym_analysis()
            median_filter_size = 3 if self._median_filter else 0

            if roi_id is not None and kym_analysis.has_analysis(roi_id):
                time_arr = kym_analysis.get_analysis_value(roi_id, "time")
                vel_arr = kym_analysis.get_analysis_value(
                    roi_id, "velocity",
                    remove_outliers=self._remove_outliers,
                    median_filter=median_filter_size,
                )
                if time_arr is not None and vel_arr is not None:
                    x_line = np.asarray(time_arr, dtype=float)
                    y_line = np.asarray(vel_arr, dtype=float)
                    self._line_plot_widget.clear_lines()
                    self._line_plot_widget.add_line(x_line, y_line, "velocity")

                    events_raw = (
                        kym_analysis.get_velocity_events_filtered(roi_id, self._event_filter or {})
                        if self._event_filter
                        else kym_analysis.get_velocity_events(roi_id)
                    )
                    acq_events = velocity_events_to_acq_image_events(events_raw)
                    self._line_plot_widget.acq_image_events.clear_all_events()
                    if acq_events:
                        self._line_plot_widget.acq_image_events.add_events(acq_events)
                    if self._selected_event_id:
                        self._line_plot_widget.acq_image_events.select_event(
                            self._selected_event_id,
                            event_window_t=0.2,
                        )
                else:
                    self._line_plot_widget.clear_lines()
            else:
                self._line_plot_widget.clear_lines()
                self._line_plot_widget.acq_image_events.clear_all_events()

            self._line_plot_widget.set_theme(theme_str)
        except Exception as e:
            logger.warning("ImageLineViewerReplacementView _refresh_from_state: %s", e)

    def set_selected_file(self, file: Optional[KymImage]) -> None:
        """Update plot for new file. Clears ROI; ROISelection will set it."""
        safe_call(self._set_selected_file_impl, file)

    def _set_selected_file_impl(self, file: Optional[KymImage]) -> None:
        if file is not None:
            try:
                file.load_channel(1)
            except Exception as exc:
                logger.warning(
                    "ImageLineViewerReplacementView failed to load channel=1: %s",
                    exc,
                )
        self._current_file = file
        self._current_roi_id = None
        self._refresh_from_state()

    def set_selected_roi(self, roi_id: Optional[int]) -> None:
        """Update plot for new ROI."""
        safe_call(self._set_selected_roi_impl, roi_id)

    def _set_selected_roi_impl(self, roi_id: Optional[int]) -> None:
        self._current_roi_id = roi_id
        self._refresh_from_state()

    def set_theme(self, theme: KymflowThemeMode) -> None:
        """Update theme for both widgets."""
        safe_call(self._set_theme_impl, theme)

    def _set_theme_impl(self, theme: KymflowThemeMode) -> None:
        self._theme = theme
        theme_str = _to_nicewidgets_theme(theme)
        if self._image_roi_widget:
            self._image_roi_widget.set_theme(theme_str)
        if self._line_plot_widget:
            self._line_plot_widget.set_theme(theme_str)

    def set_image_display(self, params: ImageDisplayParams) -> None:
        """Update colorscale/contrast on ImageRoiWidget."""
        safe_call(self._set_image_display_impl, params)

    def _set_image_display_impl(self, params: ImageDisplayParams) -> None:
        self._display_params = params
        if self._image_roi_widget and params:
            self._image_roi_widget.set_colorscale(params.colorscale)
            self._image_roi_widget.set_contrast(zmin=params.zmin, zmax=params.zmax)

    def zoom_to_event(self, e: EventSelection) -> None:
        """Update selected event highlight and optionally zoom x-axis to event."""
        safe_call(self._zoom_to_event_impl, e)

    def _zoom_to_event_impl(self, e: EventSelection) -> None:
        self._selected_event_id = e.event_id
        self._refresh_from_state()
        if (
            e.event_id
            and e.event
            and e.options
            and e.options.zoom
            and self._line_plot_widget
        ):
            pad = float(e.options.zoom_pad_sec)
            self._line_plot_widget.acq_image_events.select_event(
                e.event_id,
                event_window_t=pad * 2,  # full window width
            )
            if self._image_roi_widget:
                self._image_roi_widget.set_x_axis_range(
                    [e.event.t_start - pad, e.event.t_start + pad]
                )

    def set_event_filter(self, event_filter: dict[str, bool] | None) -> None:
        """Set event type filter. Triggers refresh."""
        self._event_filter = event_filter
        self._refresh_from_state()

    def apply_filters(self, remove_outliers: bool, median_filter: bool) -> None:
        """Apply filter settings. Triggers refresh."""
        self._remove_outliers = remove_outliers
        self._median_filter = median_filter
        self._refresh_from_state()

    def reset_zoom(self) -> None:
        """Reset zoom to full scale."""
        if self._image_roi_widget:
            self._image_roi_widget.set_x_axis_autorange()
        if self._line_plot_widget:
            self._line_plot_widget.set_x_axis_autorange()

    def scroll_x(self, direction: Literal["prev", "next"]) -> None:
        """Scroll x-axis by one window width. Clamps to data time bounds."""
        safe_call(self._scroll_x_impl, direction)

    def _get_scroll_x_time_bounds(self) -> tuple[float, float] | None:
        """Return (time_min, time_max) for the current file/ROI, or None."""
        if self._current_file is None:
            return None
        if self._current_roi_id is not None:
            tb = self._current_file.get_kym_analysis().get_time_bounds(
                self._current_roi_id
            )
            if tb is not None:
                return tb
        dur = self._current_file.image_dur
        if dur is not None:
            return (0.0, float(dur))
        return None

    def _scroll_x_impl(self, direction: Literal["prev", "next"]) -> None:
        if self._line_plot_widget is None or self._image_roi_widget is None:
            return
        layout = self._line_plot_widget.plot_dict.get("layout") or {}
        xaxis = layout.get("xaxis") or {}
        rng = xaxis.get("range")
        if not isinstance(rng, (list, tuple)) or len(rng) != 2:
            return
        try:
            x_min, x_max = float(rng[0]), float(rng[1])
        except (TypeError, ValueError):
            return
        width = x_max - x_min
        if width <= 0:
            return
        time_bounds = self._get_scroll_x_time_bounds()
        if time_bounds is None:
            return
        t_min, t_max = time_bounds
        if direction == "prev":
            new_min = max(t_min, x_min - width)
            new_max = new_min + width
            if new_max > t_max:
                new_max = t_max
                new_min = max(t_min, new_max - width)
        else:
            new_max = min(t_max, x_max + width)
            new_min = new_max - width
            if new_min < t_min:
                new_min = t_min
                new_max = min(t_max, new_min + width)
        x_range = [new_min, new_max]
        self._line_plot_widget.set_x_axis_range(x_range)
        self._image_roi_widget.set_x_axis_range(x_range)

    def set_kym_event_range_enabled(
        self,
        enabled: bool,
        *,
        event_id: Optional[str] = None,
        roi_id: Optional[int] = None,
        path: Optional[str] = None,
    ) -> None:
        """Stub: add-user-event API not yet in LinePlotWidget. No-op."""
        pass

    def refresh_velocity_events(self) -> None:
        """Re-refresh to pick up event changes."""
        self._refresh_from_state()
