"""Controller for handling analysis start/cancel events from the UI.

This module provides a controller that translates user analysis intents
(AnalysisStart and AnalysisCancel phase="intent") into task executions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.core.state import TaskState
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.tasks import run_flow_analysis
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import AnalysisCancel, AnalysisStart
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class AnalysisController:
    """Apply analysis start/cancel events to task execution.

    This controller handles analysis intent events from the UI (typically
    from the analysis toolbar) and starts or cancels analysis tasks.

    Update Flow:
        1. User clicks "Analyze Flow" → AnalysisToolbarView emits AnalysisStart(phase="intent")
        2. This controller receives event → calls run_flow_analysis()
        3. Task runs in background thread with TaskState updates
        4. TaskStateBridge emits TaskStateChanged events → views update

    Attributes:
        _app_state: AppState instance to access selected file.
        _task_state: TaskState instance for tracking analysis progress.
    """

    def __init__(self, app_state: AppState, task_state: TaskState, bus: EventBus) -> None:
        """Initialize analysis controller.

        Subscribes to AnalysisStart and AnalysisCancel (phase="intent") events from the bus.

        Args:
            app_state: AppState instance to access selected file.
            task_state: TaskState instance for tracking analysis progress.
            bus: EventBus instance to subscribe to.
        """
        self._app_state: AppState = app_state
        self._task_state: TaskState = task_state
        bus.subscribe_intent(AnalysisStart, self._on_analysis_start)
        bus.subscribe_intent(AnalysisCancel, self._on_analysis_cancel)

    def _on_analysis_start(self, e: AnalysisStart) -> None:
        """Handle analysis start intent event.

        Starts flow analysis on the currently selected file. Shows a notification
        if no file is selected or no ROI is selected.

        Args:
            e: AnalysisStart event (phase="intent") containing window_size and roi_id.
        """
        kf = self._app_state.selected_file
        if not kf:
            ui.notify("Select a file first", color="warning")
            return

        # Require ROI selection before starting analysis
        if e.roi_id is None:
            ui.notify("ROI selection required", color="warning")
            return

        # Start analysis in background thread
        run_flow_analysis(
            kf,
            self._task_state,
            window_size=e.window_size,
            roi_id=e.roi_id,
            on_result=lambda success: self._on_analysis_complete(kf, success),
        )

    def _on_analysis_complete(self, kf, success: bool) -> None:
        """Handle analysis completion callback.

        Called by run_flow_analysis when analysis completes. Updates AppState
        to notify that metadata has changed (analysis results are stored in the file).

        Args:
            kf: KymImage instance that was analyzed.
            success: Whether analysis completed successfully.
        """
        if success:
            self._app_state.update_metadata(kf)
            self._app_state.refresh_file_rows()

    def _on_analysis_cancel(self, e: AnalysisCancel) -> None:
        """Handle analysis cancel intent event.

        Requests cancellation of the current analysis task.

        Args:
            e: AnalysisCancel event (phase="intent").
        """
        self._task_state.request_cancel()
