"""Bindings between KymEventView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import (
    DetectEvents,
    KymEventSelection,
    FileSelection,
    KymEvent,
    KymEventAction,
    ROISelection,
    SelectionOrigin,
    SetKymEventXRange,
)
from kymflow.gui_v2.events_state import FileListChanged, InteractionBlocked
from kymflow.gui_v2.views.kym_event_view import KymEventView
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage
    from kymflow.gui_v2.state import AppState


class KymEventBindings:
    """Bind KymEventView to event bus for state → view updates."""

    def __init__(self, bus: EventBus, view: KymEventView, app_state: "AppState | None" = None) -> None:
        self._bus: EventBus = bus
        self._view: KymEventView = view
        self._app_state: "AppState | None" = app_state
        self._subscribed: bool = False
        self._current_file: KymImage | None = None
        self._logger = get_logger(__name__)

        bus.subscribe_state(FileSelection, self._on_file_selection_changed)
        bus.subscribe_state(ROISelection, self._on_roi_selection_changed)
        bus.subscribe_state(KymEventSelection, self._on_event_selection_changed)
        bus.subscribe_intent(SetKymEventXRange, self._on_kym_event_x_range)
        bus.subscribe_state(KymEvent, self._on_kym_event)
        bus.subscribe_state(DetectEvents, self._on_detect_events_done)
        bus.subscribe(FileListChanged, self._on_file_list_changed)
        bus.subscribe_state(InteractionBlocked, self._on_interaction_blocked)
        self._subscribed = True

    def teardown(self) -> None:
        if not self._subscribed:
            return
        self._bus.unsubscribe_state(FileSelection, self._on_file_selection_changed)
        self._bus.unsubscribe_state(ROISelection, self._on_roi_selection_changed)
        self._bus.unsubscribe_state(KymEventSelection, self._on_event_selection_changed)
        self._bus.unsubscribe_intent(SetKymEventXRange, self._on_kym_event_x_range)
        self._bus.unsubscribe_state(KymEvent, self._on_kym_event)
        self._bus.unsubscribe_state(DetectEvents, self._on_detect_events_done)
        self._bus.unsubscribe(FileListChanged, self._on_file_list_changed)
        self._bus.unsubscribe_state(InteractionBlocked, self._on_interaction_blocked)
        self._subscribed = False

    def _on_file_selection_changed(self, e: FileSelection) -> None:
        self._current_file = e.file
        if e.file is None:
            safe_call(self._view.set_events, [])
            safe_call(self._view.set_selected_event_ids, [], origin=SelectionOrigin.EXTERNAL)
            # Update file path label to show "No file selected"
            self._view._current_file_path = None
            # safe_call(self._view._update_file_path_label)  # Commented out - aggrid has 'file' column
            return
        # Update file path from the selected file (even if no events exist)
        if hasattr(e.file, "path") and e.file.path:
            self._view._current_file_path = str(e.file.path)
            # safe_call(self._view._update_file_path_label)  # Commented out - aggrid has 'file' column
        blinded = self._view._app_context.app_config.get_blinded() if self._view._app_context.app_config else False
        report = e.file.get_kym_analysis().get_velocity_report(blinded=blinded)
        safe_call(self._view.set_events, report)
        # ROI filter for Add Event / table filter: prefer FileSelection.roi_id, else AppState.
        roi_for_events = e.roi_id
        if roi_for_events is None and self._app_state is not None:
            roi_for_events = self._app_state.selected_roi_id
        safe_call(self._view.set_selected_roi, roi_for_events)
        # Clear event selection on file change (kym_event_selection is always None on file change)
        # This replaces the KymEventSelection(event_id=None) that was previously emitted
        safe_call(self._view.set_selected_event_ids, [], origin=SelectionOrigin.EXTERNAL)

    def _on_roi_selection_changed(self, e: ROISelection) -> None:
        # Still call set_selected_roi to update filter state, but it will skip set_data
        # if we originated a FileSelection (handled inside set_selected_roi)
        # logger.debug(f'e: {e}')
        safe_call(self._view.set_selected_roi, e.roi_id)

    def _on_event_selection_changed(self, e: KymEventSelection) -> None:
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
        # self._logger.debug("received SetKymEventXRange event_id=%s", e.event_id)
        safe_call(self._view.handle_set_kym_event_x_range, e)

    def _on_kym_event(self, e: KymEvent) -> None:
        """Update event table after KymEvent state (ADD/EDIT/DELETE)."""
        if self._current_file is None:
            return
        blinded = (
            self._view._app_context.app_config.get_blinded()
            if self._view._app_context.app_config
            else False
        )
        if e.action == KymEventAction.ADD:
            report = self._current_file.get_kym_analysis().get_velocity_report(blinded=blinded)
            # Selection is driven by AppState → bridge → KymEventSelection(state);
            # KymEventController calls select_velocity_event after ADD.
            safe_call(self._view.set_events, report)
        elif e.action == KymEventAction.EDIT:
            if e.event_id is not None and self._view._grid is not None:
                row = self._current_file.get_kym_analysis().get_velocity_event_row(
                    e.event_id, blinded=blinded
                )
                if row is not None:
                    safe_call(self._view.update_row_for_event, row)
                    safe_call(
                        self._view.set_selected_event_ids,
                        [e.event_id],
                        origin=SelectionOrigin.EXTERNAL,
                    )
                    return
            report = self._current_file.get_kym_analysis().get_velocity_report(blinded=blinded)
            safe_call(self._view.set_events, report)
            if e.event_id:
                safe_call(
                    self._view.set_selected_event_ids,
                    [e.event_id],
                    origin=SelectionOrigin.EXTERNAL,
                )
        elif e.action == KymEventAction.DELETE:
            report = self._current_file.get_kym_analysis().get_velocity_report(blinded=blinded)
            safe_call(self._view.set_events, report)
            safe_call(
                self._view.set_selected_event_ids,
                [],
                origin=SelectionOrigin.EXTERNAL,
            )

    def _on_detect_events_done(self, e: DetectEvents) -> None:
        """Refresh event table rows after event detection completes."""
        if self._current_file is None:
            return
        # Check if event path matches current file (if path is provided)
        if e.path is not None and self._current_file.path is not None:
            if str(self._current_file.path) != e.path:
                # Event is for a different file, ignore
                return
        self._logger.debug("detect_events_done(state) roi_id=%s", e.roi_id)
        blinded = self._view._app_context.app_config.get_blinded() if self._view._app_context.app_config else False
        report = self._current_file.get_kym_analysis().get_velocity_report(blinded=blinded)
        safe_call(self._view.set_events, report)
        # Clear selection when new events are detected
        safe_call(
            self._view.set_selected_event_ids,
            [],
            origin=SelectionOrigin.EXTERNAL,
        )

    def _on_file_list_changed(self, e: FileListChanged) -> None:
        """Handle file list change event.

        Single-file mode handles its own updates, so no action needed here.
        """
        pass

    def _on_interaction_blocked(self, e: InteractionBlocked) -> None:
        """Forward interaction blocking state to the view for nuanced handling."""
        safe_call(self._view._on_interaction_blocked, e)
