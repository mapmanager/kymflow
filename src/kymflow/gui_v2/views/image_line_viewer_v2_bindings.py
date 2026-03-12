"""Bindings between ImageLineViewerV2View and event bus.

Phase 3: wires the v2 view (ImageRoiWidget + LinePlotWidget) to
AppState events. No SetRoiEditState (ROI edit is ImageRoiWidget built-in only).
"""

from __future__ import annotations

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import (
    AddKymEvent,
    ChannelSelection,
    DeleteKymEvent,
    DeleteRoi,
    DetectEvents,
    EditPhysicalUnits,
    EditRoi,
    EventSelection,
    FileChanged,
    FileSelection,
    KymScrollXEvent,
    ROISelection,
    ImageDisplayChange,
    SelectionOrigin,
    SetKymEventRangeState,
    SetRoiBounds,
    VelocityEventUpdate,
)
from kymflow.gui_v2.events_state import AnalysisCompleted, ThemeChanged
from kymflow.gui_v2.views.image_line_viewer_v2_view import (
    ImageLineViewerV2View,
)
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


class ImageLineViewerV2Bindings:
    """Bind ImageLineViewerV2View to event bus.

    Same event subscription pattern as ImageLineViewerBindings but targets
    the v2 view. No SetRoiEditState; VelocityEventUpdate, AddKymEvent,
    DeleteKymEvent use refresh_velocity_events (no Plotly CRUD).
    """

    def __init__(self, bus: EventBus, view: ImageLineViewerV2View) -> None:
        self._bus = bus
        self._view = view
        self._subscribed = False

        bus.subscribe_state(FileSelection, self._on_file_selection_changed)
        bus.subscribe_state(FileChanged, self._on_file_changed)
        bus.subscribe_state(ROISelection, self._on_roi_changed)
        bus.subscribe_state(EventSelection, self._on_event_selected)
        bus.subscribe(ThemeChanged, self._on_theme_changed)
        bus.subscribe_state(ImageDisplayChange, self._on_image_display_changed)
        bus.subscribe_state(ChannelSelection, self._on_channel_selection_changed)
        bus.subscribe_state(EditPhysicalUnits, self._on_edit_physical_units)
        bus.subscribe_state(AnalysisCompleted, self._on_analysis_completed)
        bus.subscribe_state(DetectEvents, self._on_detect_events_done)
        bus.subscribe_state(SetKymEventRangeState, self._on_kym_event_range_state)
        bus.subscribe_state(VelocityEventUpdate, self._on_velocity_event_update)
        bus.subscribe_state(AddKymEvent, self._on_add_kym_event)
        bus.subscribe_state(DeleteKymEvent, self._on_delete_kym_event)
        bus.subscribe_intent(SetRoiBounds, self._on_roi_bounds)
        bus.subscribe_intent(KymScrollXEvent, self._on_kym_scroll_x)
        self._subscribed = True

    def teardown(self) -> None:
        if not self._subscribed:
            return
        self._bus.unsubscribe_state(FileSelection, self._on_file_selection_changed)
        self._bus.unsubscribe_state(FileChanged, self._on_file_changed)
        self._bus.unsubscribe_state(ROISelection, self._on_roi_changed)
        self._bus.unsubscribe_state(EventSelection, self._on_event_selected)
        self._bus.unsubscribe(ThemeChanged, self._on_theme_changed)
        self._bus.unsubscribe_state(ImageDisplayChange, self._on_image_display_changed)
        self._bus.unsubscribe_state(ChannelSelection, self._on_channel_selection_changed)
        self._bus.unsubscribe_state(EditPhysicalUnits, self._on_edit_physical_units)
        self._bus.unsubscribe_state(AnalysisCompleted, self._on_analysis_completed)
        self._bus.unsubscribe_state(DetectEvents, self._on_detect_events_done)
        self._bus.unsubscribe_state(SetKymEventRangeState, self._on_kym_event_range_state)
        self._bus.unsubscribe_state(VelocityEventUpdate, self._on_velocity_event_update)
        self._bus.unsubscribe_state(AddKymEvent, self._on_add_kym_event)
        self._bus.unsubscribe_state(DeleteKymEvent, self._on_delete_kym_event)
        self._bus.unsubscribe_intent(SetRoiBounds, self._on_roi_bounds)
        self._bus.unsubscribe_intent(KymScrollXEvent, self._on_kym_scroll_x)
        self._subscribed = False

    def _on_file_selection_changed(self, e: FileSelection) -> None:
        """Update view with full selection state (file, channel, roi_id) from the event.
        ROI is set as part of set_selected_file; ROISelection is handled in _on_roi_changed."""
        safe_call(self._view.set_selected_file, e.file, e.channel, e.roi_id)
        safe_call(
            self._view.zoom_to_event,
            EventSelection(
                event_id=None,
                roi_id=None,
                path=None,
                event=None,
                options=None,
                origin=e.origin,
                phase="state",
            ),
        )

    def _on_file_changed(self, e: FileChanged) -> None:
        """Handle FileChanged state events and refresh ROIs when needed.

        This binding listens for FileChanged events with change_type="roi" for the
        currently displayed file and triggers a pull-based ROI refresh on the view.

        Args:
            e: FileChanged state event describing which file changed and why.
        """
        # Only care about ROI-related changes.
        if e.change_type != "roi":
            return
        current = self._view._current_file
        if current is None:
            return
        # Compare by path to avoid issues with different KymImage instances
        # that refer to the same on-disk file.
        if not getattr(current, "path", None):
            return
        if str(e.file.path) != str(current.path):
            return
        safe_call(self._view.refresh_rois_for_current_file)

    def _on_roi_changed(self, e: ROISelection) -> None:
        # For FILE_TABLE origin, FileSelection already set ROI; avoid duplicate work.
        if e.origin == SelectionOrigin.FILE_TABLE:
            return
        safe_call(self._view.set_selected_roi, e.roi_id)

    def _on_theme_changed(self, e: ThemeChanged) -> None:
        safe_call(self._view.set_theme, e.theme)

    def _on_image_display_changed(self, e: ImageDisplayChange) -> None:
        safe_call(self._view.set_image_display, e.params)

    def _on_channel_selection_changed(self, e: ChannelSelection) -> None:
        """Handle channel selection change event (state)."""
        # TODO: extend ImageLineViewerV2View with set_selected_channel if needed.
        # For now, rely on ImageRoiWidget's own channel handling; this is a hook for future use.
        pass

    def _on_edit_physical_units(self, e: EditPhysicalUnits) -> None:
        current = self._view._current_file
        if current is None:
            return
        if str(e.file.path) != str(current.path):
            return
        # Physical units affect both image and line; do a full refresh.
        safe_call(self._view._refresh_from_state)

    def _on_analysis_completed(self, e: AnalysisCompleted) -> None:
        if not e.success:
            return
        current = self._view._current_file
        if current is None:
            return
        if str(e.file.path) != str(current.path):
            return
        # Recompute line + events for current ROI when analysis completes.
        safe_call(self._view.refresh_velocity_events)

    def _on_detect_events_done(self, e: DetectEvents) -> None:
        current = self._view._current_file
        if current is None:
            return
        if e.path and current.path and str(current.path) != e.path:
            return
        # DetectEvents only affects event rectangles.
        safe_call(self._view.refresh_events_for_current_roi)

    def _on_event_selected(self, e: EventSelection) -> None:
        safe_call(self._view.zoom_to_event, e)

    def _on_kym_event_range_state(self, e: SetKymEventRangeState) -> None:
        safe_call(
            self._view.set_kym_event_range_enabled,
            e.enabled,
            event_id=e.event_id,
            roi_id=e.roi_id,
            path=e.path,
        )

    def _on_velocity_event_update(self, e: VelocityEventUpdate) -> None:
        # VelocityEventUpdate only affects event rectangles.
        safe_call(self._view.refresh_events_for_current_roi)

    def _on_add_kym_event(self, e: AddKymEvent) -> None:
        # AddKymEvent only affects event rectangles.
        safe_call(self._view.refresh_events_for_current_roi)

    def _on_delete_kym_event(self, e: DeleteKymEvent) -> None:
        # DeleteKymEvent only affects event rectangles.
        safe_call(self._view.refresh_events_for_current_roi)

    def _on_roi_bounds(self, e: SetRoiBounds) -> None:
        from kymflow.core.image_loaders.roi import RoiBounds
        from kymflow.gui_v2.events import EditRoi

        bounds = RoiBounds(
            dim0_start=int(min(e.y0, e.y1)),
            dim0_stop=int(max(e.y0, e.y1)),
            dim1_start=int(min(e.x0, e.x1)),
            dim1_stop=int(max(e.x0, e.x1)),
        )
        self._bus.emit(
            EditRoi(
                roi_id=e.roi_id if e.roi_id is not None else 0,
                bounds=bounds,
                path=e.path,
                origin=e.origin,
                phase="intent",
            )
        )

    def _on_kym_scroll_x(self, e: KymScrollXEvent) -> None:
        safe_call(self._view.scroll_x, e.direction)

    # ROI Edit/Delete state events are no longer required for view updates.
    # Structural ROI changes are handled via FileChanged(state, change_type="roi")
    # and selection changes via ROISelection(state), so we do not subscribe to
    # EditRoi or DeleteRoi state here.
