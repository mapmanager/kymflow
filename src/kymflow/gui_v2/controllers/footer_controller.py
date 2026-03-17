"""Footer controller wiring AppState and EventBus into FooterView.

Responsibilities:
- Listen to selection state events and update the footer summary (file · channel · ROI).
- Listen to TaskStateChanged (task_type='home') and mirror progress into the footer.
- Listen to high-level intent events (analyze, save, load) to populate the "last event" text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import (
    AnalysisStart,
    FileSelection,
    ROISelection,
    SaveAll,
    SaveSelected,
)
from kymflow.gui_v2.events_folder import SelectPathEvent
from kymflow.gui_v2.events_state import TaskStateChanged, FooterStatusMessage
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.views.footer_view import FooterView
from kymflow.core.utils.logging import get_logger


logger = get_logger(__name__)


class FooterController:
    """Controller that feeds selection, status, and progress into the footer."""

    def __init__(self, app_state: AppState, bus: EventBus, view: FooterView) -> None:
        self._app_state = app_state
        self._bus = bus
        self._view = view

        # Local cached state for composing labels
        self._file_name: Optional[str] = None
        self._roi_id: Optional[int] = None
        # Channel selection is currently implicit (ImageLineViewerView loads channel=1),
        # so we expose a simple, explicit label for clarity.
        self._channel_label: Optional[str] = "Ch1"

        # Subscriptions
        bus.subscribe_state(FileSelection, self._on_file_selection_state)
        bus.subscribe_state(ROISelection, self._on_roi_selection_state)
        bus.subscribe_state(TaskStateChanged, self._on_task_state_changed)
        bus.subscribe(FooterStatusMessage, self._on_footer_status_message)

        bus.subscribe_intent(AnalysisStart, self._on_analysis_start_intent)
        bus.subscribe_intent(SaveSelected, self._on_save_selected_intent)
        bus.subscribe_intent(SaveAll, self._on_save_all_intent)
        bus.subscribe_intent(SelectPathEvent, self._on_select_path_intent)

    # --- Selection summary -------------------------------------------------

    def _on_file_selection_state(self, e: FileSelection) -> None:
        """Update footer when file selection (state) changes."""
        file_obj = e.file
        if file_obj is not None and hasattr(file_obj, "path"):
            name = Path(file_obj.path).name  # type: ignore[arg-type]
        else:
            name = None

        self._file_name = name
        # Use ROI carried on the FileSelection state event when present
        self._roi_id = e.roi_id
        self._update_selection_view()

    def _on_roi_selection_state(self, e: ROISelection) -> None:
        """Update footer when ROI selection (state) changes."""
        self._roi_id = e.roi_id
        self._update_selection_view()

    def _update_selection_view(self) -> None:
        """Push current selection summary into the view."""
        self._view.set_selection_summary(
            file_name=self._file_name,
            channel_label=self._channel_label,
            roi_id=self._roi_id,
        )

    # --- Last event text from high-level intents ---------------------------

    def _on_analysis_start_intent(self, e: AnalysisStart) -> None:
        self._view.set_last_event("Analysis: starting flow analysis", level="none")

    def _on_save_selected_intent(self, e: SaveSelected) -> None:
        self._view.set_last_event("Save: saving selected file", level="none")

    def _on_save_all_intent(self, e: SaveAll) -> None:
        self._view.set_last_event("Save: saving all files", level="none")

    def _on_select_path_intent(self, e: SelectPathEvent) -> None:
        path = Path(e.new_path)
        label = path.name or str(path)
        self._view.set_last_event(f"Load: {label}", level="none")

    def _on_footer_status_message(self, e: FooterStatusMessage) -> None:
        """Handle ad-hoc footer status messages.

        This provides a simple, global way for GUI controllers/views to set the
        footer status text (and warning/error styling) without wiring dedicated
        events for each case.

        Note: task-driven messages (from TaskStateChanged) may later overwrite
        this text when tasks start or finish; that's intentional so long-running
        operations remain the primary status source while active.
        """
        self._view.set_last_event(e.text, level=e.level)

    # --- Progress bar + status from TaskStateChanged ----------------------

    def _on_task_state_changed(self, e: TaskStateChanged) -> None:
        """Mirror TaskStateChanged into footer progress + status."""
        if e.task_type not in ("home", "load"):
            return

        # Determine a message prefix based on task type
        prefix = "Task"
        if e.task_type == "home":
            prefix = "Task"
        elif e.task_type == "load":
            prefix = "Load"

        message = e.message or ""
        display_message = f"{prefix}: {message}" if message else prefix

        if e.running:
            # Task is active: show progress bar with current status.
            self._view.set_progress(
                running=True,
                progress=e.progress,
                message=display_message,
            )
            # For very first tick (progress may still be 0), also treat as a start event.
            # Use level="none" to clear any previous warning/error styling.
            if e.progress == 0.0:
                self._view.set_last_event(display_message, level="none")
        else:
            # Task finished: hide progress bar, but keep a concise final status in last-event.
            self._view.set_progress(
                running=False,
                progress=0.0,
                message="",
            )
            if message:
                self._view.set_last_event(display_message, level="none")

