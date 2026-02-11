"""Bindings between ImageLineViewerView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import (
    AddKymEvent,
    DeleteKymEvent,
    DeleteRoi,
    DetectEvents,
    EditPhysicalUnits,
    EditRoi,
    EventSelection,
    FileSelection,
    ROISelection,
    ImageDisplayChange,
    SetKymEventRangeState,
    SetRoiBounds,
    SetRoiEditState,
    VelocityEventUpdate,
)
from kymflow.gui_v2.events_state import AnalysisCompleted, ThemeChanged
from kymflow.gui_v2.views.image_line_viewer_view import ImageLineViewerView
from kymflow.core.utils.logging import get_logger
from kymflow.core.plotting.line_plots import (
    add_kym_event_rect,
    delete_kym_event_rect,
    move_kym_event_rect,
    select_kym_event_rect,
)

if TYPE_CHECKING:
    pass


class ImageLineViewerBindings:
    """Bind ImageLineViewerView to event bus for state → view updates.

    This class subscribes to state change events from AppState (via the bridge)
    and updates the image/line viewer view accordingly. The viewer is reactive
    and doesn't initiate actions (except for ROI dropdown, which emits intent events).

    Event Flow:
        1. FileSelection(phase="state") → view.set_selected_file()
        2. ROISelection(phase="state") → view.set_selected_roi()
        3. ThemeChanged → view.set_theme()
        4. ImageDisplayChange(phase="state") → view.set_image_display()

    Attributes:
        _bus: EventBus instance for subscribing to events.
        _view: ImageLineViewerView instance to update.
        _subscribed: Whether subscriptions are active (for cleanup).
    """

    def __init__(self, bus: EventBus, view: ImageLineViewerView) -> None:
        """Initialize image/line viewer bindings.

        Subscribes to state change events. Since EventBus now uses per-client
        isolation and deduplicates handlers, duplicate subscriptions are automatically
        prevented.

        Args:
            bus: EventBus instance for this client.
            view: ImageLineViewerView instance to update.
        """
        self._bus: EventBus = bus
        self._view: ImageLineViewerView = view
        self._subscribed: bool = False

        # Subscribe to state change events
        bus.subscribe_state(FileSelection, self._on_file_selection_changed)
        bus.subscribe_state(ROISelection, self._on_roi_changed)
        bus.subscribe_state(EventSelection, self._on_event_selected)
        bus.subscribe(ThemeChanged, self._on_theme_changed)
        bus.subscribe_state(ImageDisplayChange, self._on_image_display_changed)
        bus.subscribe_state(EditPhysicalUnits, self._on_edit_physical_units)
        bus.subscribe_state(AnalysisCompleted, self._on_analysis_completed)
        bus.subscribe_state(DetectEvents, self._on_detect_events_done)
        bus.subscribe_state(SetKymEventRangeState, self._on_kym_event_range_state)
        bus.subscribe_state(VelocityEventUpdate, self._on_velocity_event_update)
        bus.subscribe_state(AddKymEvent, self._on_add_kym_event)
        bus.subscribe_state(DeleteKymEvent, self._on_delete_kym_event)
        bus.subscribe_state(SetRoiEditState, self._on_roi_edit_state)
        bus.subscribe_state(EditRoi, self._on_roi_edited)
        bus.subscribe_state(DeleteRoi, self._on_roi_deleted)
        bus.subscribe_intent(SetRoiBounds, self._on_roi_bounds)
        self._subscribed = True

        self._logger = get_logger(__name__)

    def teardown(self) -> None:
        """Unsubscribe from all events (cleanup).

        Call this when the bindings are no longer needed (e.g., page destroyed).
        EventBus per-client isolation means this is usually not necessary, but
        it's available for explicit cleanup if needed.
        """
        if not self._subscribed:
            return

        self._bus.unsubscribe_state(FileSelection, self._on_file_selection_changed)
        self._bus.unsubscribe_state(ROISelection, self._on_roi_changed)
        self._bus.unsubscribe_state(EventSelection, self._on_event_selected)
        self._bus.unsubscribe(ThemeChanged, self._on_theme_changed)
        self._bus.unsubscribe_state(ImageDisplayChange, self._on_image_display_changed)
        self._bus.unsubscribe_state(EditPhysicalUnits, self._on_edit_physical_units)
        self._bus.unsubscribe_state(AnalysisCompleted, self._on_analysis_completed)
        self._bus.unsubscribe_state(DetectEvents, self._on_detect_events_done)
        self._bus.unsubscribe_state(SetKymEventRangeState, self._on_kym_event_range_state)
        self._bus.unsubscribe_state(VelocityEventUpdate, self._on_velocity_event_update)
        self._bus.unsubscribe_state(AddKymEvent, self._on_add_kym_event)
        self._bus.unsubscribe_state(DeleteKymEvent, self._on_delete_kym_event)
        self._bus.unsubscribe_state(SetRoiEditState, self._on_roi_edit_state)
        self._bus.unsubscribe_state(EditRoi, self._on_roi_edited)
        self._bus.unsubscribe_state(DeleteRoi, self._on_roi_deleted)
        self._bus.unsubscribe_intent(SetRoiBounds, self._on_roi_bounds)
        self._subscribed = False

    def _on_file_selection_changed(self, e: FileSelection) -> None:
        """Handle file selection change event.

        Updates viewer for new file selection, ROI selection, and clears event zoom.
        Wrapped in safe_call to handle deleted client errors gracefully.

        Args:
            e: FileSelection event (phase="state") containing the selected file, roi_id, and kym_event_selection.
        """
        safe_call(self._view.set_selected_file, e.file)
        # Update ROI selection from FileSelection (replaces separate ROISelection emission)
        safe_call(self._view.set_selected_roi, e.roi_id)
        # Clear event zoom on file change (kym_event_selection is always None on file change)
        # Create a None EventSelection to pass to zoom_to_event for clearing
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

    def _on_roi_changed(self, e: ROISelection) -> None:
        """Handle ROI selection change event.

        Updates viewer for new ROI selection. Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: ROISelection event (phase="state") containing the selected ROI ID.
        """
        safe_call(self._view.set_selected_roi, e.roi_id)

    def _on_theme_changed(self, e: ThemeChanged) -> None:
        """Handle theme change event.

        Updates viewer theme. Wrapped in safe_call to handle deleted client
        errors gracefully.

        Args:
            e: ThemeChanged event containing the new theme mode.
        """
        safe_call(self._view.set_theme, e.theme)

    def _on_image_display_changed(self, e: ImageDisplayChange) -> None:
        """Handle image display parameter change event.

        Updates viewer contrast/colorscale. Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: ImageDisplayChange event (phase="state") containing the new display parameters.
        """
        safe_call(self._view.set_image_display, e.params)

    def _on_edit_physical_units(self, e: EditPhysicalUnits) -> None:
        """Handle EditPhysicalUnits event by refreshing plot if it matches current file.
        
        Physical units changes affect the plot axes and scaling, so we need to refresh
        the entire plot when they change.
        
        Args:
            e: EditPhysicalUnits event (phase="state") containing the file whose physical units were updated.
        """
        self._logger.debug(
            "EditPhysicalUnits(state) received: file.path=%s, seconds_per_line=%s, um_per_pixel=%s",
            e.file.path if e.file and hasattr(e.file, "path") else None,
            e.seconds_per_line,
            e.um_per_pixel,
        )
        
        # Only refresh if this event is for the currently displayed file
        current_file = self._view._current_file  # noqa: SLF001
        if current_file is None:
            self._logger.debug("EditPhysicalUnits: current_file is None, ignoring")
            return
        
        self._logger.debug(
            "EditPhysicalUnits: current_file.path=%s, event.file.path=%s",
            current_file.path if hasattr(current_file, "path") else None,
            e.file.path if e.file and hasattr(e.file, "path") else None,
        )
        
        # Check if the event's file matches the currently displayed file by path
        # Use path comparison for reliability (file objects may be different instances)
        if e.file.path is not None and current_file.path is not None:
            if str(e.file.path) != str(current_file.path):
                # Event is for a different file, ignore
                self._logger.debug(
                    "EditPhysicalUnits: path mismatch (event=%s, current=%s), ignoring",
                    e.file.path,
                    current_file.path,
                )
                return
        
        # Refresh the plot to reflect new physical units (full refresh)
        self._logger.debug("EditPhysicalUnits: calling _render_combined() to refresh plot")
        safe_call(self._view._render_combined)  # noqa: SLF001

    def _on_analysis_completed(self, e: AnalysisCompleted) -> None:
        """Handle analysis completion by refreshing plot for current file."""
        if not e.success:
            return
        
        # Only refresh if this event is for the currently displayed file
        current_file = self._view._current_file  # noqa: SLF001
        if current_file is None:
            return
        
        # Check if the event's file matches the currently displayed file by path
        # Use path comparison for reliability (file objects may be different instances)
        if e.file.path is not None and current_file.path is not None:
            if str(e.file.path) != str(current_file.path):
                # Event is for a different file, ignore
                return
        
        # Refresh the plot to reflect completed analysis
        safe_call(self._view._render_combined)  # noqa: SLF001

    def _on_detect_events_done(self, e: DetectEvents) -> None:
        """Handle DetectEvents completion by refreshing velocity event overlays.
        
        Similar to how FileSelection triggers a full refresh, DetectEvents
        triggers a refresh of velocity event overlays to show newly detected events.
        
        Args:
            e: DetectEvents event (phase="state") containing roi_id and path.
        """
        # Only refresh if this event is for the currently displayed file
        current_file = self._view._current_file
        if current_file is None:
            return
        
        # For all-files mode, always refresh (events could be in any file)
        # Commented out: Detect Events (all files) disabled
        # if e.all_files:
        #     safe_call(self._view.refresh_velocity_events)
        #     return
        
        # For single-file mode, only refresh if path matches current file
        if e.path is not None and current_file.path is not None:
            if str(current_file.path) != e.path:
                # Event is for a different file, ignore
                return
        
        # Refresh velocity event overlays (preserves zoom)
        safe_call(self._view.refresh_velocity_events)

    def _on_event_selected(self, e: EventSelection) -> None:
        """Handle EventSelection change event."""
        safe_call(self._view.zoom_to_event, e)

    def _on_kym_event_range_state(self, e: SetKymEventRangeState) -> None:
        """Handle kym event range state change."""

        # self._logger.debug(
        #     "kym_event_range_state(enabled=%s, event_id=%s)", e.enabled, e.event_id
        # )

        safe_call(
            self._view.set_kym_event_range_enabled,
            e.enabled,
            event_id=e.event_id,
            roi_id=e.roi_id,
            path=e.path,
        )

    def _on_velocity_event_update(self, e: VelocityEventUpdate) -> None:
        """Handle velocity event updates using CRUD operations (no full render).
        
        Args:
            e: VelocityEventUpdate state event containing event_id, updates, etc.
        """
        self._logger.debug("velocity_event_update(state) event_id=%s", e.event_id)
        
        # Check if we can use CRUD (dict-based update)
        if self._view._current_figure_dict is None:  # noqa: SLF001
            self._logger.error(
                "velocity_event_update: _current_figure_dict is None, falling back to full render. "
                "This should not happen!"
            )
            safe_call(self._view.refresh_velocity_events)
            return
        
        # Validate we have required state
        if self._view._current_file is None:  # noqa: SLF001
            self._logger.warning("velocity_event_update: _current_file is None, skipping")
            return
        
        if self._view._current_roi_id is None:  # noqa: SLF001
            self._logger.warning("velocity_event_update: _current_roi_id is None, skipping")
            return
        
        # Get updated event from KymAnalysis
        kym_analysis = self._view._current_file.get_kym_analysis()  # noqa: SLF001
        result = kym_analysis.find_event_by_uuid(e.event_id)
        if result is None:
            self._logger.warning(
                "velocity_event_update: event not found (event_id=%s), skipping", e.event_id
            )
            return
        
        roi_id, index, event = result
        
        # Validate ROI match
        if roi_id != self._view._current_roi_id:  # noqa: SLF001
            self._logger.error(
                "velocity_event_update: ROI mismatch - event roi_id=%s, current roi_id=%s. "
                "Cross-ROI operations not allowed.",
                roi_id,
                self._view._current_roi_id,  # noqa: SLF001
            )
            return
        
        # Get time_range for coordinate calculation
        if not kym_analysis.has_analysis(roi_id):
            self._logger.warning(
                "velocity_event_update: no analysis for roi_id=%s, skipping", roi_id
            )
            return
        
        time_range = kym_analysis.get_time_bounds(roi_id)
        if time_range is None:
            self._logger.warning(
                "velocity_event_update: no time bounds for roi_id=%s, skipping", roi_id
            )
            return
        
        # Check if event was selected
        is_selected = (
            self._view._selected_event_id is not None  # noqa: SLF001
            and e.event_id == self._view._selected_event_id  # noqa: SLF001
        )
        
        # Use CRUD to move/update event rect
        try:
            move_kym_event_rect(
                self._view._current_figure_dict,  # noqa: SLF001
                event,
                time_range,
                row=2,
            )
            
            # If event was selected, update selection styling
            if is_selected:
                select_kym_event_rect(
                    self._view._current_figure_dict,  # noqa: SLF001
                    event,
                    row=2,
                )
            
            # Update the plot
            self._view.ui_plotly_update_figure()
        except RuntimeError as ex:
            self._logger.error(f"Error updating figure: {ex}")
            if "deleted" not in str(ex).lower():
                raise

    def _on_add_kym_event(self, e: AddKymEvent) -> None:
        """Handle add kym event using CRUD operations (no full render).
        
        Args:
            e: AddKymEvent state event containing event_id, roi_id, etc.
        """
        self._logger.debug("add_kym_event(state) event_id=%s", e.event_id)
        
        # Check if we can use CRUD (dict-based update)
        if self._view._current_figure_dict is None:  # noqa: SLF001
            self._logger.error(
                "add_kym_event: _current_figure_dict is None, falling back to full render. "
                "This should not happen!"
            )
            safe_call(self._view.refresh_velocity_events)
            # Reset dragmode to zoom (disable selection mode)
            safe_call(
                self._view.set_kym_event_range_enabled,
                False,
                event_id=None,
                roi_id=None,
                path=None,
            )
            return
        
        # Validate we have required state
        if self._view._current_file is None:  # noqa: SLF001
            self._logger.warning("add_kym_event: _current_file is None, skipping")
            return
        
        if self._view._current_roi_id is None:  # noqa: SLF001
            self._logger.warning("add_kym_event: _current_roi_id is None, skipping")
            return
        
        # Validate ROI match
        if e.roi_id != self._view._current_roi_id:  # noqa: SLF001
            self._logger.error(
                "add_kym_event: ROI mismatch - event roi_id=%s, current roi_id=%s. "
                "Cross-ROI operations not allowed.",
                e.roi_id,
                self._view._current_roi_id,  # noqa: SLF001
            )
            return
        
        # Get event from KymAnalysis
        kym_analysis = self._view._current_file.get_kym_analysis()  # noqa: SLF001
        if e.event_id is None:
            self._logger.warning("add_kym_event: event_id is None, skipping")
            return
        
        result = kym_analysis.find_event_by_uuid(e.event_id)
        if result is None:
            self._logger.warning(
                "add_kym_event: event not found (event_id=%s), skipping", e.event_id
            )
            return
        
        roi_id, index, event = result
        
        # Get time_range for coordinate calculation
        if not kym_analysis.has_analysis(roi_id):
            self._logger.warning(
                "add_kym_event: no analysis for roi_id=%s, skipping", roi_id
            )
            return
        
        time_range = kym_analysis.get_time_bounds(roi_id)
        if time_range is None:
            self._logger.warning(
                "add_kym_event: no time bounds for roi_id=%s, skipping", roi_id
            )
            return
        
        # Use CRUD to add a single event rect for the newly added event
        try:
            add_kym_event_rect(
                self._view._current_figure_dict,  # noqa: SLF001
                event,
                time_range,
                row=2,
            )
            # Select the newly added event (highlight it)
            select_kym_event_rect(
                self._view._current_figure_dict,  # noqa: SLF001
                event,
                row=2,
            )
            # Update the plot
            self._view.ui_plotly_update_figure()
        except RuntimeError as ex:
            self._logger.error(f"Error updating figure: {ex}")
            if "deleted" not in str(ex).lower():
                raise
        
        # Reset dragmode to zoom (disable selection mode)
        safe_call(
            self._view.set_kym_event_range_enabled,
            False,
            event_id=None,
            roi_id=None,
            path=None,
        )

    def _on_delete_kym_event(self, e: DeleteKymEvent) -> None:
        """Handle delete kym event using CRUD operations (no full render).
        
        Args:
            e: DeleteKymEvent state event containing event_id, roi_id, etc.
        """
        self._logger.debug("delete_kym_event(state) event_id=%s", e.event_id)
        
        # Check if we can use CRUD (dict-based update)
        if self._view._current_figure_dict is None:  # noqa: SLF001
            self._logger.error(
                "delete_kym_event: _current_figure_dict is None, falling back to full render. "
                "This should not happen!"
            )
            safe_call(self._view.refresh_velocity_events)
            return
        
        # Check if deleted event was selected
        was_selected = (
            self._view._selected_event_id is not None  # noqa: SLF001
            and e.event_id == self._view._selected_event_id  # noqa: SLF001
        )
        
        # Use CRUD to delete event rect
        try:
            delete_kym_event_rect(
                self._view._current_figure_dict,  # noqa: SLF001
                e.event_id,
                row=2,
            )
            
            # If deleted event was selected, deselect all
            if was_selected:
                select_kym_event_rect(
                    self._view._current_figure_dict,  # noqa: SLF001
                    None,
                    row=2,
                )
            
            # Update the plot
            self._view.ui_plotly_update_figure()
        except RuntimeError as ex:
            self._logger.error(f"Error updating figure: {ex}")
            if "deleted" not in str(ex).lower():
                raise

    def _on_roi_edit_state(self, e: SetRoiEditState) -> None:
        """Handle ROI edit state change."""
        self._logger.debug(
            "roi_edit_state(enabled=%s, roi_id=%s)", e.enabled, e.roi_id
        )
        safe_call(
            self._view.set_roi_edit_enabled,
            e.enabled,
            roi_id=e.roi_id,
            path=e.path,
        )

    def _on_roi_bounds(self, e: SetRoiBounds) -> None:
        """Handle SetRoiBounds intent event - convert to EditRoi."""
        self._logger.debug(
            "roi_bounds(intent) roi_id=%s x=[%s, %s] y=[%s, %s]",
            e.roi_id,
            e.x0,
            e.x1,
            e.y0,
            e.y1,
        )
        from kymflow.core.image_loaders.roi import RoiBounds

        # Convert Plotly coordinates to RoiBounds
        bounds = RoiBounds(
            dim0_start=int(min(e.y0, e.y1)),
            dim0_stop=int(max(e.y0, e.y1)),
            dim1_start=int(min(e.x0, e.x1)),
            dim1_stop=int(max(e.x0, e.x1)),
        )
        
        # Emit EditRoi intent event
        from kymflow.gui_v2.events import EditRoi
        self._bus.emit(
            EditRoi(
                roi_id=e.roi_id if e.roi_id is not None else 0,
                bounds=bounds,
                path=e.path,
                origin=e.origin,
                phase="intent",
            )
        )

    def _on_roi_edited(self, e: EditRoi) -> None:
        """Handle ROI edited state event - refresh plot."""
        self._logger.debug("roi_edited(state) roi_id=%s", e.roi_id)
        # Refresh plot with updated ROI bounds
        safe_call(self._view.set_selected_roi, e.roi_id)

    def _on_roi_deleted(self, e: DeleteRoi) -> None:
        """Handle ROI deleted state event - refresh plot."""
        self._logger.debug("roi_deleted(state) roi_id=%s", e.roi_id)
        # Refresh plot
        safe_call(self._view._render_combined)
