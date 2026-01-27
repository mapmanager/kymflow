"""Bindings between AnalysisToolbarView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import AddRoi, DeleteRoi, EditRoi, FileSelection, ROISelection
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.gui_v2.views.analysis_toolbar_view import AnalysisToolbarView

if TYPE_CHECKING:
    pass


class AnalysisToolbarBindings:
    """Bind AnalysisToolbarView to event bus for state → view updates.

    This class subscribes to state change events from AppState and TaskState
    (via the bridge) and updates the analysis toolbar view accordingly. The view
    is reactive and doesn't initiate actions (except for user interactions,
    which emit intent events).

    Event Flow:
        1. FileSelection(phase="state") → view.set_selected_file()
        2. ROISelection(phase="state") → view.set_selected_roi()
        3. TaskStateChanged → view.set_task_state() (update button states)

    Attributes:
        _bus: EventBus instance for subscribing to events.
        _view: AnalysisToolbarView instance to update.
        _subscribed: Whether subscriptions are active (for cleanup).
    """

    def __init__(self, bus: EventBus, view: AnalysisToolbarView) -> None:
        """Initialize analysis toolbar bindings.

        Subscribes to state change events. Since EventBus now uses per-client
        isolation and deduplicates handlers, duplicate subscriptions are automatically
        prevented.

        Args:
            bus: EventBus instance for this client.
            view: AnalysisToolbarView instance to update.
        """
        self._bus: EventBus = bus
        self._view: AnalysisToolbarView = view
        self._subscribed: bool = False

        # Subscribe to state change events
        bus.subscribe_state(FileSelection, self._on_file_selection_changed)
        bus.subscribe_state(ROISelection, self._on_roi_selection_changed)
        bus.subscribe_state(TaskStateChanged, self._on_task_state_changed)
        bus.subscribe_state(AddRoi, self._on_roi_state_changed)
        bus.subscribe_state(DeleteRoi, self._on_roi_state_changed)
        bus.subscribe_state(EditRoi, self._on_roi_state_changed)
        self._subscribed = True

    def teardown(self) -> None:
        """Unsubscribe from all events (cleanup).

        Call this when the bindings are no longer needed (e.g., page destroyed).
        EventBus per-client isolation means this is usually not necessary, but
        it's available for explicit cleanup if needed.
        """
        if not self._subscribed:
            return

        self._bus.unsubscribe_state(FileSelection, self._on_file_selection_changed)
        self._bus.unsubscribe_state(ROISelection, self._on_roi_selection_changed)
        self._bus.unsubscribe_state(TaskStateChanged, self._on_task_state_changed)
        self._bus.unsubscribe_state(AddRoi, self._on_roi_state_changed)
        self._bus.unsubscribe_state(DeleteRoi, self._on_roi_state_changed)
        self._bus.unsubscribe_state(EditRoi, self._on_roi_state_changed)
        self._subscribed = False

    def _on_file_selection_changed(self, e: FileSelection) -> None:
        """Handle file selection change event.

        Updates view for new file selection. Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: FileSelection event (phase="state") containing the selected file.
        """
        safe_call(self._view.set_selected_file, e.file)

    def _on_roi_selection_changed(self, e: ROISelection) -> None:
        """Handle ROI selection change event.

        Updates view for new ROI selection. Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: ROISelection event (phase="state") containing the selected ROI ID.
        """
        safe_call(self._view.set_selected_roi, e.roi_id)

    def _on_task_state_changed(self, e: TaskStateChanged) -> None:
        """Handle task state change event.

        Updates view button states based on task running/cancellable state.
        Only processes events for "home" task type. Wrapped in safe_call to handle
        deleted client errors gracefully.

        Args:
            e: TaskStateChanged event containing task state information.
        """
        from kymflow.core.utils.logging import get_logger
        logger = get_logger(__name__)
        
        # logger.debug(
        #     f"Received TaskStateChanged: task_type={e.task_type}, running={e.running}, "
        #     f"cancellable={e.cancellable}, progress={e.progress}"
        # )
        
        # Only process "home" task type events for this toolbar
        if e.task_type == "home":
            # logger.debug(f"Processing TaskStateChanged for home task, calling set_task_state")
            safe_call(self._view.set_task_state, e)
        else:
            # logger.debug(f"Ignoring TaskStateChanged for task_type={e.task_type} (not 'home')")
            pass

    def _on_roi_state_changed(self, e: AddRoi | DeleteRoi | EditRoi) -> None:
        """Handle ROI state change events (AddRoi, DeleteRoi, EditRoi).

        Updates button states and ROI dropdown when ROI operations complete.

        Args:
            e: ROI event (phase="state") indicating ROI was added, deleted, or edited.
        """
        safe_call(self._view._update_button_states)
        safe_call(self._view._update_roi_dropdown)