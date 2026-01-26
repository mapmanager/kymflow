"""Bindings between ImageLineViewerView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import (
    AddKymEvent,
    DeleteKymEvent,
    EventSelection,
    FileSelection,
    ROISelection,
    ImageDisplayChange,
    MetadataUpdate,
    SetKymEventRangeState,
    VelocityEventUpdate,
)
from kymflow.gui_v2.events_state import ThemeChanged
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
        bus.subscribe_state(MetadataUpdate, self._on_metadata_changed)
        bus.subscribe_state(SetKymEventRangeState, self._on_kym_event_range_state)
        bus.subscribe_state(VelocityEventUpdate, self._on_velocity_event_update)
        bus.subscribe_state(AddKymEvent, self._on_add_kym_event)
        bus.subscribe_state(DeleteKymEvent, self._on_delete_kym_event)
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
        self._bus.unsubscribe_state(SetKymEventRangeState, self._on_kym_event_range_state)
        self._bus.unsubscribe_state(VelocityEventUpdate, self._on_velocity_event_update)
        self._bus.unsubscribe_state(AddKymEvent, self._on_add_kym_event)
        self._bus.unsubscribe_state(DeleteKymEvent, self._on_delete_kym_event)
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
