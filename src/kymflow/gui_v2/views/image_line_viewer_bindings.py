"""Bindings between ImageLineViewerView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import (
    AddKymEvent,
    DeleteKymEvent,
    DeleteRoi,
    EditRoi,
    EventSelection,
    FileSelection,
    ROISelection,
    ImageDisplayChange,
    MetadataUpdate,
    SetKymEventRangeState,
    SetRoiBounds,
    SetRoiEditState,
    VelocityEventUpdate,
)
from kymflow.gui_v2.events_state import AnalysisCompleted, ThemeChanged
from kymflow.gui_v2.views.image_line_viewer_view import ImageLineViewerView
from kymflow.core.utils.logging import get_logger

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
        5. MetadataUpdate(phase="state") → view.set_metadata() (only if file matches current)

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
        
        # abb we have this so our plotly plots update after 'analyze flow'
        bus.subscribe_state(MetadataUpdate, self._on_metadata_changed)
        
        bus.subscribe_state(AnalysisCompleted, self._on_analysis_completed)
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
        self._bus.unsubscribe_state(MetadataUpdate, self._on_metadata_changed)
        self._bus.unsubscribe_state(AnalysisCompleted, self._on_analysis_completed)
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

        Updates viewer for new file selection. Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: FileSelection event (phase="state") containing the selected file.
        """
        safe_call(self._view.set_selected_file, e.file)

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

    def _on_metadata_changed(self, e: MetadataUpdate) -> None:
        """Handle metadata change event.

        Refreshes viewer if the updated file matches the currently selected file.
        Wrapped in safe_call to handle deleted client errors gracefully.

        Args:
            e: MetadataUpdate event (phase="state") containing the file whose metadata was updated.
        """
        safe_call(self._view.set_metadata, e.file)

    def _on_analysis_completed(self, e: AnalysisCompleted) -> None:
        """Handle analysis completion by refreshing plot for current file."""
        if e.success and e.file == self._view._current_file:  # noqa: SLF001
            safe_call(self._view._render_combined)

    def _on_event_selected(self, e: EventSelection) -> None:
        """Handle EventSelection change event."""
        safe_call(self._view.zoom_to_event, e)

    def _on_kym_event_range_state(self, e: SetKymEventRangeState) -> None:
        """Handle kym event range state change."""
        self._logger.debug(
            "kym_event_range_state(enabled=%s, event_id=%s)", e.enabled, e.event_id
        )
        safe_call(
            self._view.set_kym_event_range_enabled,
            e.enabled,
            event_id=e.event_id,
            roi_id=e.roi_id,
            path=e.path,
        )

    def _on_velocity_event_update(self, e: VelocityEventUpdate) -> None:
        """Handle velocity event updates by refreshing overlays."""
        self._logger.debug("velocity_event_update(state) event_id=%s", e.event_id)
        safe_call(self._view.refresh_velocity_events)

    def _on_add_kym_event(self, e: AddKymEvent) -> None:
        """Handle add kym event by refreshing overlays and resetting dragmode."""
        self._logger.debug("add_kym_event(state) event_id=%s", e.event_id)
        safe_call(self._view.refresh_velocity_events)
        # Reset dragmode to zoom (disable selection mode)
        safe_call(
            self._view.set_kym_event_range_enabled,
            False,
            event_id=None,
            roi_id=None,
            path=None,
        )

    def _on_delete_kym_event(self, e: DeleteKymEvent) -> None:
        """Handle delete kym event by refreshing overlays."""
        self._logger.debug("delete_kym_event(state) event_id=%s", e.event_id)
        safe_call(self._view.refresh_velocity_events)

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
