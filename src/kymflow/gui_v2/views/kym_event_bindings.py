"""Bindings between KymEventView and event bus (state → view updates)."""

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
    SelectionOrigin,
    SetKymEventXRange,
    VelocityEventUpdate,
)
from kymflow.gui_v2.views.kym_event_view import KymEventView
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage


class KymEventBindings:
    """Bind KymEventView to event bus for state → view updates."""

    def __init__(self, bus: EventBus, view: KymEventView) -> None:
        self._bus: EventBus = bus
        self._view: KymEventView = view
        self._subscribed: bool = False
        self._current_file: KymImage | None = None
        self._logger = get_logger(__name__)

        bus.subscribe_state(FileSelection, self._on_file_selection_changed)
        bus.subscribe_state(ROISelection, self._on_roi_selection_changed)
        bus.subscribe_state(EventSelection, self._on_event_selection_changed)
        bus.subscribe_intent(SetKymEventXRange, self._on_kym_event_x_range)
        bus.subscribe_state(VelocityEventUpdate, self._on_velocity_event_update)
        bus.subscribe_state(AddKymEvent, self._on_add_kym_event)
        bus.subscribe_state(DeleteKymEvent, self._on_delete_kym_event)
        self._subscribed = True

    def teardown(self) -> None:
        if not self._subscribed:
            return
        self._bus.unsubscribe_state(FileSelection, self._on_file_selection_changed)
        self._bus.unsubscribe_state(ROISelection, self._on_roi_selection_changed)
        self._bus.unsubscribe_state(EventSelection, self._on_event_selection_changed)
        self._bus.unsubscribe_intent(SetKymEventXRange, self._on_kym_event_x_range)
        self._bus.unsubscribe_state(VelocityEventUpdate, self._on_velocity_event_update)
        self._bus.unsubscribe_state(AddKymEvent, self._on_add_kym_event)
        self._bus.unsubscribe_state(DeleteKymEvent, self._on_delete_kym_event)
        self._subscribed = False

    def _on_file_selection_changed(self, e: FileSelection) -> None:
        self._current_file = e.file
        if e.file is None:
            safe_call(self._view.set_events, [])
            safe_call(self._view.set_selected_event_ids, [], origin=SelectionOrigin.EXTERNAL)
            # Update file path label to show "No file selected"
            self._view._current_file_path = None
            safe_call(self._view._update_file_path_label)
            return
        # Update file path from the selected file (even if no events exist)
        if hasattr(e.file, "path") and e.file.path:
            self._view._current_file_path = str(e.file.path)
            safe_call(self._view._update_file_path_label)
        report = e.file.get_kym_analysis().get_velocity_report()
        safe_call(self._view.set_events, report)

    def _on_roi_selection_changed(self, e: ROISelection) -> None:
        safe_call(self._view.set_selected_roi, e.roi_id)

    def _on_event_selection_changed(self, e: EventSelection) -> None:
        if e.origin == SelectionOrigin.EVENT_TABLE:
            return
        if e.event_id is None:
            safe_call(self._view.set_selected_event_ids, [], origin=SelectionOrigin.EXTERNAL)
        else:
            safe_call(
                self._view.set_selected_event_ids,
                [e.event_id],
                origin=SelectionOrigin.EXTERNAL,
            )

    def _on_kym_event_x_range(self, e: SetKymEventXRange) -> None:
        self._logger.debug("received SetKymEventXRange event_id=%s", e.event_id)
        safe_call(self._view.handle_set_kym_event_x_range, e)

    def _on_velocity_event_update(self, e: VelocityEventUpdate) -> None:
        """Refresh event table rows after updates."""
        if self._current_file is None:
            return
        self._logger.debug("velocity_event_update(state) event_id=%s", e.event_id)
        report = self._current_file.get_kym_analysis().get_velocity_report()
        safe_call(self._view.set_events, report)
        if e.event_id:
            safe_call(
                self._view.set_selected_event_ids,
                [e.event_id],
                origin=SelectionOrigin.EXTERNAL,
            )

    def _on_add_kym_event(self, e: AddKymEvent) -> None:
        """Refresh event table rows after adding new event."""
        if self._current_file is None:
            return
        self._logger.debug("add_kym_event(state) event_id=%s", e.event_id)
        report = self._current_file.get_kym_analysis().get_velocity_report()
        # Select the newly created event during set_events to ensure proper timing
        safe_call(
            self._view.set_events,
            report,
            select_event_id=e.event_id if e.event_id else None,
        )

    def _on_delete_kym_event(self, e: DeleteKymEvent) -> None:
        """Refresh event table rows after deleting event and clear selection."""
        if self._current_file is None:
            return
        self._logger.debug("delete_kym_event(state) event_id=%s", e.event_id)
        report = self._current_file.get_kym_analysis().get_velocity_report()
        safe_call(self._view.set_events, report)
        # Clear selection since the event was deleted
        safe_call(
            self._view.set_selected_event_ids,
            [],
            origin=SelectionOrigin.EXTERNAL,
        )
