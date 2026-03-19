"""Image/line viewer v2 using nicewidgets ImageRoiWidget and LinePlotWidget.

Phase 2 of the migration plan: composes ImageRoiWidget (kymograph image) and
LinePlotWidget (velocity line + event rects) in a vertical layout.
Phase 3: wired via ImageLineViewerV2Bindings.
Phase 4: swap into home_page.
Phase 5: drawer filter/zoom wired; apply_filters, reset_zoom, scroll_x, set_event_filter.
Phase 6: ROI edit (ROIEvent UPDATE → EditRoi); recursion fix (suppress ROI select emit when syncing from state).
"""

from __future__ import annotations

from typing import Callable, Literal, Optional
from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.roi import RectROI, RoiBounds
from kymflow.core.plotting.theme import ThemeMode as KymflowThemeMode
from kymflow.gui_v2.adapters import (
    create_full_roi_for_widget,
    kymimage_to_channel_manager,
    velocity_events_to_acq_image_events,
)
from kymflow.gui_v2.state import ImageDisplayParams
from kymflow.gui_v2.events import (
    AddKymEvent,
    ChannelSelection,
    DeleteKymEvent,
    DeleteRoi,
    EditRoi,
    EventSelection,
    SelectionOrigin,
    SetKymEventXRange,
    SetRoiBounds,
    VelocityEventUpdate,
)
from kymflow.gui_v2.client_utils import safe_call
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

OnKymEventXRange = Callable[[SetKymEventXRange], None]
OnSetRoiBounds = Callable[[SetRoiBounds], None]
OnRoiSelect = Callable[[int | None], None]
OnEditRoi = Callable[[EditRoi], None]
OnAddRoi = Callable[[int], None]
OnDeleteRoi = Callable[[DeleteRoi], None]
OnChannelSelect = Callable[[ChannelSelection], None]


def _region_of_interest_to_roi_bounds(roi) -> RoiBounds:
    """Convert nicewidgets RegionOfInterest to kymflow RoiBounds.
    r0,r1=rows=dim0, c0,c1=cols=dim1.
    """
    
    return RoiBounds(
        dim0_start=int(min(roi.r0, roi.r1)),
        dim0_stop=int(max(roi.r0, roi.r1)),
        dim1_start=int(min(roi.c0, roi.c1)),
        dim1_stop=int(max(roi.c0, roi.c1)),
    )


def _parse_roi_id_from_name(name: str) -> int | None:
    """Parse roi_id from RegionOfInterest name for widget->app events.

    kymflow uses roi_id (int) as the canonical identifier. The adapter creates
    names as str(roi_id) (e.g. "1", "2"). ImageRoiWidget may add ROIs with
    "ROI_N" format. Supports both: bare int string and "ROI_<int>".
    """
    if not name:
        return None
    try:
        return int(name)
    except ValueError:
        pass
    if name.startswith("ROI_"):
        try:
            return int(name.split("_", 1)[1])
        except (IndexError, ValueError):
            pass
    return None


def _to_nicewidgets_theme(kymflow_theme: KymflowThemeMode) -> str:
    """Map kymflow ThemeMode to nicewidgets-compatible theme string."""
    return "dark" if kymflow_theme is KymflowThemeMode.DARK else "light"


def _rectroi_to_region_of_interest(roi_id: int, rect: RectROI):
    """Convert kymflow RectROI to nicewidgets RegionOfInterest.

    Uses RoiBounds dim0 as rows (r0/r1) and dim1 as cols (c0/c1), matching
    _region_of_interest_to_roi_bounds in the opposite direction.
    """
    from nicewidgets.image_line_widget.models import RegionOfInterest

    b = rect.bounds
    return RegionOfInterest(
        name=str(roi_id),
        r0=int(b.dim0_start),
        r1=int(b.dim0_stop),
        c0=int(b.dim1_start),
        c1=int(b.dim1_stop),
    )


class ImageLineViewerV2View:
    """V2 view composing ImageRoiWidget and LinePlotWidget.

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
        on_add_roi: OnAddRoi | None = None,
        on_delete_roi: OnDeleteRoi | None = None,
    ) -> None:
        self._on_kym_event_x_range = on_kym_event_x_range
        self._on_set_roi_bounds = on_set_roi_bounds
        self._on_roi_select = on_roi_select
        self._on_edit_roi = on_edit_roi
        self._on_add_roi = on_add_roi
        self._on_delete_roi = on_delete_roi
        self._on_channel_select: OnChannelSelect | None = None

        self._suppress_roi_select_emit = False
        self._container: Optional[ui.element] = None
        self._image_roi_widget = None
        self._line_plot_widget = None
        self._contrast_widget = None

        self._current_file: Optional[KymImage] = None
        self._current_channel: Optional[int] = None
        self._current_roi_id: Optional[int] = None
        self._theme: KymflowThemeMode = KymflowThemeMode.DARK
        self._display_params: Optional[ImageDisplayParams] = None
        self._selected_event_id: Optional[str] = None
        self._event_filter: Optional[dict[str, bool]] = None
        self._syncing_axes = False
        self._kym_event_range_event_id: Optional[str] = None
        self._kym_event_range_roi_id: Optional[int] = None
        self._kym_event_range_path: Optional[str] = None
        # Combined widget instance (ImageLineCombinedWidget); set in render().
        self._combined = None

    def render(self) -> None:
        """Create the viewer UI: ImageRoiWidget + LinePlotWidget in a column."""
        from nicewidgets.image_line_widget.image_contrast_widget import ImageContrastWidget
        from nicewidgets.image_line_widget.image_line_combined_widget import (
            ImageLineCombinedWidget,
        )
        from nicewidgets.image_line_widget.models import (
            AxisEvent,
            ChannelEvent,
            ContrastEvent,
            ROIEvent,
            ROIEventType,
        )

        # Important for nested splitters: allow children to fully shrink.
        self._container = ui.column().classes("w-full h-full min-h-0")
        with self._container:
            theme_str = _to_nicewidgets_theme(self._theme)

            def on_contrast_changed(ev: ContrastEvent) -> None:
                """Apply contrast and colorscale changes from contrast widget locally."""
                if self._image_roi_widget is None:
                    return
                self._image_roi_widget.set_contrast_fast(zmin=ev.zmin, zmax=ev.zmax)
                self._image_roi_widget.set_colorscale(ev.color_lut)

            def on_channel_event(ev: ChannelEvent) -> None:
                """Update contrast widget image when user changes the active channel."""
                if self._image_roi_widget is None or self._contrast_widget is None:
                    return
                manager = self._image_roi_widget.manager
                names = list(manager.channels.keys())
                if ev.channel_name not in names:
                    return
                idx = names.index(ev.channel_name)
                ch = manager.channels[ev.channel_name]
                # Treat channel as opaque int defined by caller; prefer parsing from name.
                try:
                    channel_int = int(ev.channel_name)
                except ValueError:
                    channel_int = idx
                self._contrast_widget.set_channel(channel_int, ch.data)
                # Emit ChannelSelection intent event upstream if callback is provided.
                if self._on_channel_select is not None:
                    from kymflow.gui_v2.events import ChannelSelection, SelectionOrigin
                    self._on_channel_select(
                        ChannelSelection(
                            channel=channel_int,
                            origin=SelectionOrigin.IMAGE_VIEWER,
                            phase="intent",
                        )
                    )

            def on_roi_event(e: ROIEvent) -> None:
                if e.type is ROIEventType.SELECT and self._on_roi_select and not self._suppress_roi_select_emit:
                    roi_id = _parse_roi_id_from_name(e.roi.name) if e.roi else None
                    self._on_roi_select(roi_id)
                elif e.type is ROIEventType.UPDATE and e.roi and self._on_edit_roi:
                    roi_id = _parse_roi_id_from_name(e.roi.name)
                    if roi_id is not None:
                        bounds = _region_of_interest_to_roi_bounds(e.roi)
                        path = str(self._current_file.path) if self._current_file else None
                        self._on_edit_roi(
                            EditRoi(
                                roi_id=roi_id,
                                bounds=bounds,
                                path=path,
                                origin=SelectionOrigin.IMAGE_VIEWER,
                                phase="intent",
                            )
                        )
                elif e.type is ROIEventType.DELETE and e.roi and self._on_delete_roi:
                    roi_id = _parse_roi_id_from_name(e.roi.name)
                    if roi_id is not None:
                        path = str(self._current_file.path) if self._current_file else None
                        self._on_delete_roi(
                            DeleteRoi(
                                roi_id=roi_id,
                                path=path,
                                origin=SelectionOrigin.IMAGE_VIEWER,
                                phase="intent",
                            )
                        )

            def on_axis_change(ev: AxisEvent) -> None:
                # abb this is handled by image line combined widget
                logger.warning('-->> xxx --> EARLY RETURN')
                return

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
            from nicewidgets.image_line_widget.models import Channel, ChannelManager

            placeholder = np.zeros((10, 10), dtype=np.float64)
            placeholder_manager = ChannelManager(
                channels=[Channel("Empty", placeholder)],
                row_scale=1.0,
                col_scale=1.0,
                x_label="Time (s)",
                y_label="Space (um)",
            )
            def on_request_add_roi():
                if self._current_file is None:
                    return None
                new_roi = create_full_roi_for_widget(self._current_file)
                if new_roi is not None and self._on_add_roi:
                    self._on_add_roi(int(new_roi.name))
                return new_roi

            # Contrast widget row (above image ROI widget)
            self._contrast_widget = ImageContrastWidget(
                widget_name="image_contrast_widget",
                on_contrast_changed=on_contrast_changed,
                theme=theme_str,
            )

            combined = ImageLineCombinedWidget(
                widget_name="image_line_combined",
                manager=placeholder_manager,
                initial_rois=[],
                on_roi_event=on_roi_event,
                on_axis_change=on_axis_change,
                on_channel_event=on_channel_event,
                on_rect_selection=None,
                on_request_add_roi=on_request_add_roi,
                theme=theme_str,
            )

            # Expose compatibility handles used throughout this view, and keep a
            # private handle to the combined widget for whole-view operations.
            self._combined = combined
            self._image_roi_widget = combined.image_roi_widget
            self._line_plot_widget = combined.line_plot_widget

        # Populate from current state if we have file/roi
        self._refresh_from_state()

    def _refresh_from_state(self) -> None:
        """Update widgets from _current_file and _current_roi_id."""
        if self._combined is None or self._image_roi_widget is None or self._line_plot_widget is None:
            return

        kf = self._current_file

        if kf is None:
            # No file: clear line + events and leave image placeholder.
            self._line_plot_widget.clear_for_no_roi()
            return

        try:
            self._switch_file_to_current_state()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("ImageLineViewerV2View _refresh_from_state failed: %s", exc)

    def _switch_file_to_current_state(self) -> None:
        """Drive the combined widget to represent the current file/ROI state.

        This batches image data, ROIs, velocity line, and velocity events into a
        single ``switch_file`` call on ``ImageLineCombinedWidget`` to avoid
        duplicated Plotly updates. Public view APIs remain unchanged; this
        helper is an internal implementation detail invoked from
        ``_refresh_from_state``.

        Args:
            None. Uses ``self._current_file``, ``self._current_roi_id``, and
            ``self._current_channel`` as implicit inputs.

        Returns:
            None. Updates the underlying combined widget in place.
        """
        if self._combined is None or self._current_file is None:
            return

        kf = self._current_file

        # Rebuild ChannelManager and ROI list exactly as before.
        manager, rois = kymimage_to_channel_manager(kf)

        # Derive velocity trace for the current ROI using existing logic.
        time_arr = None
        vel_arr = None
        if self._current_roi_id is not None:
            kym_analysis = kf.get_kym_analysis()
            radon = kym_analysis.get_analysis_object("RadonAnalysis")
            channel = radon.get_channel_for_roi(self._current_roi_id) if radon else None
            if radon is not None and channel is not None and radon.has_analysis(self._current_roi_id, channel):
                time_arr = radon.get_analysis_value(self._current_roi_id, channel, "time")
                vel_arr = radon.get_analysis_value(self._current_roi_id, channel, "velocity")

        # Derive events for the current ROI/channel using existing logic.
        acq_events = []
        if self._current_roi_id is not None and self._current_channel is not None:
            kym_analysis = kf.get_kym_analysis()
            if self._event_filter:
                events_raw = kym_analysis.get_velocity_events_filtered(
                    self._current_roi_id, self._current_channel, self._event_filter
                )
            else:
                events_raw = kym_analysis.get_velocity_events(self._current_roi_id, self._current_channel)
            acq_events = velocity_events_to_acq_image_events(events_raw) or []

        # Single combined update for image + line + events (including ROI selection).
        selected_roi_name = str(self._current_roi_id) if self._current_roi_id is not None else None
        self._combined.switch_file(
            manager,
            rois,
            velocity_x=time_arr,
            velocity_y=vel_arr,
            events=acq_events,
            reset_axes=True,
            selected_roi_name=selected_roi_name,
        )

        # Re-apply display params and contrast state (selection is handled in switch_file).
        self._apply_display_params_and_selection(manager)

    def _apply_display_params_and_selection(self, manager) -> None:
        """Re-apply colorscale/contrast, ROI selection, and contrast state.

        This helper reapplies view-local image display parameters and ROI
        selection after a combined ``switch_file`` update, and keeps the
        separate contrast widget in sync with the active channel.

        Args:
            manager: The current ``ChannelManager`` associated with the
                displayed image.

        Returns:
            None. Mutates ``_image_roi_widget`` and ``_contrast_widget`` state.
        """
        if self._image_roi_widget is None:
            return

        if self._display_params:
            self._image_roi_widget.set_colorscale(self._display_params.colorscale)
            if self._display_params.zmin is not None or self._display_params.zmax is not None:
                self._image_roi_widget.set_contrast(
                    zmin=self._display_params.zmin,
                    zmax=self._display_params.zmax,
                )
        # ROI selection on the image widget is handled inside the combined switch_file
        # call when using ImageLineCombinedWidget; here we only need to sync the
        # separate contrast widget's notion of the active ROI.

        # Sync contrast widget with new image and display params (view-local only).
        if self._contrast_widget is not None:
            names = list(manager.channels.keys())
            if names:
                active_name = manager.active_channel_name
                if active_name not in names:
                    active_name = names[0]
                ch = manager.channels[active_name]
                # Treat channel as opaque int defined by caller; derive from name when possible.
                try:
                    channel_idx = int(active_name)
                except ValueError:
                    channel_idx = names.index(active_name)
                self._contrast_widget.set_channel(channel_idx, ch.data)
                self._contrast_widget.select_roi_by_index(self._current_roi_id)
                if self._display_params:
                    self._contrast_widget.set_colorscale(self._display_params.colorscale)
                    self._contrast_widget.set_contrast(
                        zmin=self._display_params.zmin,
                        zmax=self._display_params.zmax,
                    )

    def _update_image_for_file_change(self) -> None:
        """Rebuild ImageRoiWidget for the current file (image + ROIs only)."""
        kf = self._current_file
        if kf is None or self._image_roi_widget is None:
            return
        # Rebuild the ChannelManager and ROI list from the current KymImage so the
        # widget reflects the latest model state.
        manager, rois = kymimage_to_channel_manager(kf)
        # set_file remains the high-level API for updating both manager and ROIs.
        self._image_roi_widget.set_file(manager, rois)
        if self._display_params:
            self._image_roi_widget.set_colorscale(self._display_params.colorscale)
            if self._display_params.zmin is not None or self._display_params.zmax is not None:
                self._image_roi_widget.set_contrast(
                    zmin=self._display_params.zmin,
                    zmax=self._display_params.zmax,
                )
        if self._current_roi_id is not None:
            self._suppress_roi_select_emit = True
            try:
                self._image_roi_widget.select_roi_by_name(str(self._current_roi_id))
            finally:
                self._suppress_roi_select_emit = False

        # Sync contrast widget with new image and display params (view-local only).
        if self._contrast_widget is not None:
            names = list(manager.channels.keys())
            if names:
                active_name = manager.active_channel_name
                if active_name not in names:
                    active_name = names[0]
                ch = manager.channels[active_name]
                # Treat channel as opaque int defined by caller; derive from name when possible.
                try:
                    channel_idx = int(active_name)
                except ValueError:
                    channel_idx = names.index(active_name)
                self._contrast_widget.set_channel(channel_idx, ch.data)
                self._contrast_widget.select_roi_by_index(self._current_roi_id)
                if self._display_params:
                    self._contrast_widget.set_colorscale(self._display_params.colorscale)
                    self._contrast_widget.set_contrast(
                        zmin=self._display_params.zmin,
                        zmax=self._display_params.zmax,
                    )

    def refresh_rois_for_current_file(self) -> None:
        """Refresh ROIs in the widget for the current file from the backing model.

        This method is intended to be called when the underlying KymImage.rois
        for the current file changes (for example, after AddRoi/EditRoi/DeleteRoi
        controllers update the model and emit FileChanged events). It rebuilds
        the ImageRoiWidget ROI shapes and keeps the current ROI selection where
        possible.
        """
        if self._image_roi_widget is None:
            return

        kf = self._current_file
        if kf is None:
            # No file: clear ROIs and selection in the widget.
            self._image_roi_widget.set_rois({})
            self._image_roi_widget.set_selected_roi(None)
            return

        # Derive the ROI mapping from the KymImage.rois container. We use the
        # ROI id as the canonical name (string) so that it remains stable across
        # updates and matches the adapter conventions.
        from nicewidgets.image_line_widget.models import RegionOfInterest

        rois_dict: dict[str, RegionOfInterest] = {}
        for roi_id in kf.rois.get_roi_ids():
            rect = kf.rois.get(roi_id)
            if rect is None:
                continue
            rois_dict[str(roi_id)] = _rectroi_to_region_of_interest(roi_id, rect)

        self._image_roi_widget.set_rois(rois_dict)

        # Preserve the current ROI selection when possible by mapping the
        # numeric id back to the string name used by the widget.
        if self._current_roi_id is not None and str(self._current_roi_id) in rois_dict:
            self._image_roi_widget.set_selected_roi(str(self._current_roi_id))
        else:
            self._image_roi_widget.set_selected_roi(None)

    def _update_line_for_current_roi(self) -> None:
        """Recompute velocity line for current file & ROI (no image changes)."""
        if self._line_plot_widget is None:
            return
        kf = self._current_file
        roi_id = self._current_roi_id
        if kf is None or roi_id is None:
            self._line_plot_widget.clear_for_no_roi()
            return
        kym_analysis = kf.get_kym_analysis()
        # Channel from metadata
        radon = kym_analysis.get_analysis_object("RadonAnalysis")
        channel = radon.get_channel_for_roi(roi_id) if radon else None
        if radon is None or channel is None or not radon.has_analysis(roi_id, channel):
            self._line_plot_widget.clear_for_no_roi()
            return
        time_arr = radon.get_analysis_value(roi_id, channel, "time")
        vel_arr = radon.get_analysis_value(roi_id, channel, "velocity")
        if time_arr is None or vel_arr is None:
            self._line_plot_widget.clear_for_no_roi()
            return
        self._line_plot_widget.set_velocity_trace(time_arr, vel_arr, name="velocity")
        self._line_plot_widget.set_x_axis_autorange()
        self._line_plot_widget.set_y_axis_autorange()

    def _update_events_for_current_roi(self) -> None:
        """Recompute velocity-event rectangles for current file & ROI only."""
        if self._line_plot_widget is None:
            return
        kf = self._current_file
        roi_id = self._current_roi_id
        channel = self._current_channel
        if kf is None or roi_id is None or channel is None:
            self._line_plot_widget.set_events([])
            return
        kym_analysis = kf.get_kym_analysis()
        if self._event_filter:
            events_raw = kym_analysis.get_velocity_events_filtered(
                roi_id, channel, self._event_filter
            )
        else:
            events_raw = kym_analysis.get_velocity_events(roi_id, channel)
        acq_events = velocity_events_to_acq_image_events(events_raw)
        # Simple, state-driven behavior: just rebuild event rectangles on the line widget.
        # Do not try to select or zoom here; Add Event and row selection have their
        # own explicit flows that operate on the current event set.
        self._line_plot_widget.set_events(acq_events or [])

    def _kym_event_plot(self) -> tuple[object, dict] | tuple[None, None]:
        """Return (plot element, plot_dict) for velocity-event rect edits."""
        if self._combined is not None:
            return self._combined.plot, self._combined.plot_dict
        if self._line_plot_widget is not None:
            return self._line_plot_widget.plot, self._line_plot_widget.plot_dict
        return None, None

    @staticmethod
    def _pop_shape_for_event_id(shapes: list, event_id: str) -> bool:
        eid = str(event_id)
        for i, s in enumerate(shapes):
            if str(s.get("event_id", "")) == eid:
                shapes.pop(i)
                return True
        return False

    def on_add_kym_event(self, e: AddKymEvent) -> None:
        """Append one event rect shape; plot.update()."""
        if e.phase != "state" or not e.event_id or self._line_plot_widget is None:
            return
        if e.path and self._current_file and str(self._current_file.path) != str(e.path):
            return
        plot, plot_dict = self._kym_event_plot()
        if plot is None:
            return
        from nicewidgets.image_line_widget.models import AcqImageEvent

        mgr = self._line_plot_widget.acq_image_events
        evt = AcqImageEvent(
            start_t=float(e.t_start),
            stop_t=float(e.t_end) if e.t_end is not None else None,
            event_type="User Added",
            user_type="unreviewed",
            event_id=str(e.event_id),
        )
        shapes = plot_dict.setdefault("layout", {}).setdefault("shapes", [])
        self._pop_shape_for_event_id(shapes, str(e.event_id))
        shapes.append(mgr._make_rect(evt, is_selected=False))
        self._selected_event_id = str(e.event_id)
        plot.update()

    def on_delete_kym_event(self, e: DeleteKymEvent) -> None:
        """Remove one event rect shape; plot.update()."""
        if e.phase != "state" or self._line_plot_widget is None:
            return
        if e.path and self._current_file and str(self._current_file.path) != str(e.path):
            return
        plot, plot_dict = self._kym_event_plot()
        if plot is None:
            return
        shapes = plot_dict.setdefault("layout", {}).setdefault("shapes", [])
        self._pop_shape_for_event_id(shapes, str(e.event_id))
        mgr = self._line_plot_widget.acq_image_events
        if mgr._selected_event_id == str(e.event_id):
            mgr._selected_event_id = None
        if self._selected_event_id == str(e.event_id):
            self._selected_event_id = None
        plot.update()

    def on_edit_kym_event(self, e: VelocityEventUpdate) -> None:
        """Pop rect for event_id, rebuild from e.velocity_event; plot.update()."""
        if e.phase != "state" or self._line_plot_widget is None:
            return
        if e.path and self._current_file and str(self._current_file.path) != str(e.path):
            return
        if e.velocity_event is None:
            return
        plot, plot_dict = self._kym_event_plot()
        if plot is None:
            return
        acq_list = velocity_events_to_acq_image_events([e.velocity_event])
        if not acq_list:
            return
        mgr = self._line_plot_widget.acq_image_events
        shapes = plot_dict.setdefault("layout", {}).setdefault("shapes", [])
        self._pop_shape_for_event_id(shapes, str(e.event_id))
        sel = mgr._selected_event_id == str(e.event_id)
        shapes.append(mgr._make_rect(acq_list[0], is_selected=sel))
        plot.update()

    def _apply_zoom_to_event(self, e: EventSelection) -> None:
        """Select and zoom to an event without recomputing data."""
        self._selected_event_id = e.event_id
        if (
            not e.event_id
            or not e.event
            or not e.options
            or not e.options.zoom
        ):
            return
        pad = float(e.options.zoom_pad_sec)
        # Prefer the combined widget's atomic API to keep this to a single
        # Plotly update for highlight + zoom.
        if self._combined is not None:
            self._combined.select_event_and_zoom(
                e.event_id,
                e.event.t_start,
                pad,
            )
        elif self._line_plot_widget is not None:
            self._line_plot_widget.acq_image_events.select_event(
                e.event_id,
                event_window_t=pad * 2,
            )
            if self._image_roi_widget:
                self._image_roi_widget.set_x_axis_range(
                    [e.event.t_start - pad, e.event.t_start + pad]
                )

    def set_selected_file(
        self,
        file: Optional[KymImage],
        channel: Optional[int],
        roi_id: Optional[int],
    ) -> None:
        """Update plot for new file selection.

        Called by bindings when FileSelection(phase="state") is received.
        Sets full selection state (file, channel, roi_id). roi_id=None means
        the file has no ROIs and is meaningful, not missing.
        """
        safe_call(self._set_selected_file_impl, file, channel, roi_id)

    def _set_selected_file_impl(
        self,
        file: Optional[KymImage],
        channel: Optional[int],
        roi_id: Optional[int],
    ) -> None:
        if file is not None:
            ch = channel if channel is not None else 1
            try:
                file.load_channel(ch)
            except Exception as exc:
                logger.error(
                    "ImageLineViewerV2View failed to load channel=%s: %s",
                    ch,
                    exc,
                )
        self._current_file = file
        self._current_channel = channel
        self._current_roi_id = roi_id
        self._refresh_from_state()

    def set_selected_roi(self, roi_id: Optional[int]) -> None:
        """Update plot for new ROI."""
        safe_call(self._set_selected_roi_impl, roi_id)

    def _set_selected_roi_impl(self, roi_id: Optional[int]) -> None:
        """Select ROI by roi_id. Name must match adapter convention (str(roi_id))."""
        self._current_roi_id = roi_id
        if self._image_roi_widget:
            name = str(roi_id) if roi_id is not None else None
            if name is not None and name not in self._image_roi_widget.rois:
                logger.error(
                    "set_selected_roi: ROI name %r not in widget (expected str(roi_id) from adapter)",
                    name,
                )
                name = None
            self._suppress_roi_select_emit = True
            try:
                self._image_roi_widget.select_roi_by_name(name, emit_select=False)
            finally:
                self._suppress_roi_select_emit = False
        if self._contrast_widget is not None:
            self._contrast_widget.select_roi_by_index(roi_id)
        self._update_line_for_current_roi()
        self._update_events_for_current_roi()

    def set_theme(self, theme: KymflowThemeMode) -> None:
        """Update theme for both widgets."""
        safe_call(self._set_theme_impl, theme)

    def _set_theme_impl(self, theme: KymflowThemeMode) -> None:
        self._theme = theme
        theme_str = _to_nicewidgets_theme(theme)
        if self._combined is not None:
            self._combined.set_theme(theme_str)
        else:
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
        if self._contrast_widget and params:
            self._contrast_widget.set_colorscale(params.colorscale)
            self._contrast_widget.set_contrast(zmin=params.zmin, zmax=params.zmax)

    def zoom_to_event(self, e: EventSelection) -> None:
        """Update selected event highlight and optionally zoom x-axis to event."""
        safe_call(self._zoom_to_event_impl, e)

    def _zoom_to_event_impl(self, e: EventSelection) -> None:
        self._apply_zoom_to_event(e)

    def set_event_filter(self, event_filter: dict[str, bool] | None) -> None:
        """Set event type filter. Triggers refresh."""
        self._event_filter = event_filter
        self._update_events_for_current_roi()

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
        # Plotly layout is variable; .get() is intentional for optional structure.
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

        # 20260318 fast
        # self._image_roi_widget.set_x_axis_range(x_range)
        self._combined.set_x_axis_range_fast(x_range[0], x_range[1])
        # line is linked to image
        # self._line_plot_widget.set_x_axis_range(x_range)

    def set_kym_event_range_enabled(
        self,
        enabled: bool,
        *,
        event_id: Optional[str] = None,
        roi_id: Optional[int] = None,
        path: Optional[str] = None,
    ) -> None:
        """Enable/disable draw-rect mode on LinePlotWidget for Add Event / Set Event Start/Stop."""
        if self._line_plot_widget is None:
            return
        if enabled:
            self._kym_event_range_event_id = event_id
            self._kym_event_range_roi_id = roi_id
            self._kym_event_range_path = path

            def _on_rect_selection(x0: float, x1: float) -> None:
                if self._on_kym_event_x_range is None:
                    return
                x_min, x_max = min(x0, x1), max(x0, x1)
                self._on_kym_event_x_range(
                    SetKymEventXRange(
                        event_id=self._kym_event_range_event_id,
                        roi_id=self._kym_event_range_roi_id,
                        path=self._kym_event_range_path,
                        x0=x_min,
                        x1=x_max,
                        origin=SelectionOrigin.EVENT_TABLE,
                        phase="intent",
                    )
                )

            self._line_plot_widget.set_on_rect_selection(_on_rect_selection)
            self._line_plot_widget.set_draw_rect_mode(True)
        else:
            self._line_plot_widget.set_on_rect_selection(None)
            self._line_plot_widget.set_draw_rect_mode(False)

    def refresh_velocity_events(self) -> None:
        """Re-refresh to pick up event changes."""
        self._update_line_for_current_roi()
        self._update_events_for_current_roi()

    def refresh_events_for_current_roi(self) -> None:
        """Refresh only velocity events for current ROI (no image or line changes)."""
        self._update_events_for_current_roi()
