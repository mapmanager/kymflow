"""Bindings between KymEventView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import (
    AddKymEvent,
    DeleteKymEvent,
    DetectEvents,
    EventSelection,
    FileSelection,
    ROISelection,
    SelectionOrigin,
    SetKymEventXRange,
    VelocityEventUpdate,
)
from kymflow.gui_v2.events_state import FileListChanged
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
        bus.subscribe_state(EventSelection, self._on_event_selection_changed)
        bus.subscribe_intent(SetKymEventXRange, self._on_kym_event_x_range)
        bus.subscribe_state(VelocityEventUpdate, self._on_velocity_event_update)
        bus.subscribe_state(AddKymEvent, self._on_add_kym_event)
        bus.subscribe_state(DeleteKymEvent, self._on_delete_kym_event)
        bus.subscribe_state(DetectEvents, self._on_detect_events_done)
        bus.subscribe(FileListChanged, self._on_file_list_changed)
        self._subscribed = True
        
        # Set up callback for all-files mode changes
        # The view will call this when checkbox is toggled
        self._view._on_all_files_mode_changed = self._refresh_all_files_events
        
        # Set up callback to get current selected file path
        if self._app_state is not None:
            self._view._get_current_selected_file_path = lambda: (
                str(self._app_state.selected_file.path) 
                if self._app_state.selected_file and hasattr(self._app_state.selected_file, "path") and self._app_state.selected_file.path
                else None
            )

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
        self._bus.unsubscribe_state(DetectEvents, self._on_detect_events_done)
        self._bus.unsubscribe(FileListChanged, self._on_file_list_changed)
        self._subscribed = False

    def _on_file_selection_changed(self, e: FileSelection) -> None:
        self._current_file = e.file
        # If all-files mode is enabled, don't change events (keep showing all files)
        if self._view._show_all_files:
            # Check if we originated this FileSelection - if so, skip refresh but keep flag
            # (we'll clear it after handling EventSelection events to prevent scroll reset)
            if self._view._file_selection_originated_from_view is not None:
                # Verify the path matches (safety check)
                event_path = str(e.file.path) if e.file and hasattr(e.file, "path") and e.file.path else None
                if event_path == self._view._file_selection_originated_from_view:
                    # We originated this, skip any refresh but keep flag for EventSelection handling
                    return
                else:
                    # Path doesn't match - clear flag (different FileSelection occurred)
                    self._view._file_selection_originated_from_view = None
            return
        # Otherwise, use single-file behavior
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

    def _on_roi_selection_changed(self, e: ROISelection) -> None:
        # Still call set_selected_roi to update filter state, but it will skip set_data
        # if we originated a FileSelection (handled inside set_selected_roi)
        # logger.debug(f'e: {e}')
        safe_call(self._view.set_selected_roi, e.roi_id)

    def _on_event_selection_changed(self, e: EventSelection) -> None:
        if e.origin == SelectionOrigin.EVENT_TABLE:
            return
        # In all-files mode, if we originated a FileSelection, skip selection updates
        # to preserve scroll position and avoid unnecessary grid operations
        if self._view._show_all_files and self._view._file_selection_originated_from_view is not None:
            # Check if this EventSelection matches the file we originated
            event_path = str(e.path) if e.path else None
            if event_path == self._view._file_selection_originated_from_view:
                # We originated this FileSelection and this EventSelection matches it
                # The row is already selected from user click, so skip programmatic updates
                # Clear the flag now that we've handled the related events
                self._view._file_selection_originated_from_view = None
                return
            # If event_id is None, this is likely the clearing event that happens before file change
            # Don't clear the flag yet - wait for the actual file change to be confirmed
            elif e.event_id is None:
                # This is the clearing event before file change - keep flag and skip update
                return
            else:
                # Different file with an event_id - clear flag and proceed normally
                self._view._file_selection_originated_from_view = None
        if e.event_id is None:
            # In all-files mode, if we have a pending event selection from a file change,
            # preserve it instead of clearing (the file change cleared AppState, but we want to keep the selection)
            if (
                self._view._show_all_files
                and self._view._pending_event_selection_after_file_change is not None
            ):
                pending_id = self._view._pending_event_selection_after_file_change
                # Restore the pending selection
                safe_call(
                    self._view.set_selected_event_ids,
                    [pending_id],
                    origin=SelectionOrigin.EXTERNAL,
                )
                # Clear the flag
                self._view._pending_event_selection_after_file_change = None
            else:
                safe_call(self._view.set_selected_event_ids, [], origin=SelectionOrigin.EXTERNAL)
        else:
            # Clear the pending flag if we're setting a different event
            self._view._pending_event_selection_after_file_change = None
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
        # If all-files mode, refresh all events
        if self._view._show_all_files:
            self._refresh_all_files_events()
            if e.event_id:
                safe_call(
                    self._view.set_selected_event_ids,
                    [e.event_id],
                    origin=SelectionOrigin.EXTERNAL,
                )
            return
        # Single-file mode: use current file
        if self._current_file is None:
            return
        self._logger.debug("velocity_event_update(state) event_id=%s", e.event_id)
        blinded = self._view._app_context.app_config.get_blinded() if self._view._app_context.app_config else False
        report = self._current_file.get_kym_analysis().get_velocity_report(blinded=blinded)
        safe_call(self._view.set_events, report)
        if e.event_id:
            safe_call(
                self._view.set_selected_event_ids,
                [e.event_id],
                origin=SelectionOrigin.EXTERNAL,
            )

    def _on_add_kym_event(self, e: AddKymEvent) -> None:
        """Refresh event table rows after adding new event."""
        # If all-files mode, refresh all events
        if self._view._show_all_files:
            self._refresh_all_files_events()
            if e.event_id:
                safe_call(
                    self._view.set_selected_event_ids,
                    [e.event_id],
                    origin=SelectionOrigin.EXTERNAL,
                )
            return
        # Single-file mode: use current file
        if self._current_file is None:
            return
        self._logger.debug("add_kym_event(state) event_id=%s", e.event_id)
        blinded = self._view._app_context.app_config.get_blinded() if self._view._app_context.app_config else False
        report = self._current_file.get_kym_analysis().get_velocity_report(blinded=blinded)
        # Select the newly created event during set_events to ensure proper timing
        safe_call(
            self._view.set_events,
            report,
            select_event_id=e.event_id if e.event_id else None,
        )

    def _on_delete_kym_event(self, e: DeleteKymEvent) -> None:
        """Refresh event table rows after deleting event and clear selection."""
        # If all-files mode, refresh all events
        if self._view._show_all_files:
            self._refresh_all_files_events()
            # Clear selection since the event was deleted
            safe_call(
                self._view.set_selected_event_ids,
                [],
                origin=SelectionOrigin.EXTERNAL,
            )
            return
        # Single-file mode: use current file
        if self._current_file is None:
            return
        self._logger.debug("delete_kym_event(state) event_id=%s", e.event_id)
        blinded = self._view._app_context.app_config.get_blinded() if self._view._app_context.app_config else False
        report = self._current_file.get_kym_analysis().get_velocity_report(blinded=blinded)
        safe_call(self._view.set_events, report)
        # Clear selection since the event was deleted
        safe_call(
            self._view.set_selected_event_ids,
            [],
            origin=SelectionOrigin.EXTERNAL,
        )

    def _on_detect_events_done(self, e: DetectEvents) -> None:
        """Refresh event table rows after event detection completes."""
        # If all-files mode, refresh all events (new events detected in any file)
        if self._view._show_all_files:
            self._refresh_all_files_events()
            # Clear selection when new events are detected
            safe_call(
                self._view.set_selected_event_ids,
                [],
                origin=SelectionOrigin.EXTERNAL,
            )
            return
        # Single-file mode: only refresh if event is for current file
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
        
        If all-files mode is enabled, refresh events from all files.
        Otherwise, no change (single-file mode handles its own updates).
        """
        if self._view._show_all_files:
            self._refresh_all_files_events()

    def _refresh_all_files_events(self) -> None:
        """Collect events from all files and update the view.
        
        If all-files mode is enabled, collect from all files.
        If disabled, refresh current file's events.
        """
        if self._view._show_all_files:
            # Check if we originated a FileSelection - if so, skip refresh to preserve column state
            if self._view._file_selection_originated_from_view is not None:
                return
            # All-files mode: collect from all files
            if self._app_state is None:
                return
            blinded = self._view._app_context.app_config.get_blinded() if self._view._app_context.app_config else False
            all_events = []
            for kym_image in self._app_state.files:
                try:
                    report = kym_image.get_kym_analysis().get_velocity_report(roi_id=None, blinded=blinded)
                    all_events.extend(report)
                except Exception:
                    # Skip files that can't be processed
                    continue
            safe_call(self._view.set_events, all_events)
        else:
            # Single-file mode: refresh current file's events
            if self._current_file is None:
                safe_call(self._view.set_events, [])
                return
            blinded = self._view._app_context.app_config.get_blinded() if self._view._app_context.app_config else False
            report = self._current_file.get_kym_analysis().get_velocity_report(blinded=blinded)
            safe_call(self._view.set_events, report)
