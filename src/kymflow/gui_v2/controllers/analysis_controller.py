"""Controller for handling analysis start/cancel events from the UI.

This module provides a controller that translates user analysis intents
(AnalysisStart and AnalysisCancel phase="intent") into task executions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.core.state import TaskState
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.tasks import run_flow_analysis
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import AnalysisCancel, AnalysisStart
from kymflow.gui_v2.events_state import AnalysisCompleted
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
        self._bus: EventBus = bus
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

        # Verify ROI exists in the selected file
        roi_ids = kf.rois.get_roi_ids()
        if e.roi_id not in roi_ids:
            logger.warning(
                "AnalysisStart: ROI %s not found in file %s (available: %s)",
                e.roi_id,
                kf.path,
                roi_ids,
            )
            ui.notify(f"ROI {e.roi_id} not found in selected file", color="warning")
            return

        # Log for debugging
        logger.info(
            "Starting analysis: file=%s, roi_id=%s, window_size=%s",
            kf.path,
            e.roi_id,
            e.window_size,
        )

        # Start analysis in background thread
        run_flow_analysis(
            kf,
            self._task_state,
            window_size=e.window_size,
            roi_id=e.roi_id,
            on_result=lambda success: self._on_analysis_complete(kf, e.roi_id, success),
        )

    def _on_analysis_complete(self, kf, roi_id: int | None, success: bool) -> None:
        """Handle analysis completion callback.

        Called by run_flow_analysis when analysis completes. Updates AppState
        to notify that metadata has changed (analysis results are stored in the file).
        
        Note: We do NOT call refresh_file_rows() here because:
        - Analysis results are stored in memory, not on disk
        - refresh_file_rows() would reload from disk, losing unsaved changes
        - The MetadataUpdate event will trigger FileTableBindings to refresh the table view
        - Only save operations should trigger refresh_file_rows() (files on disk changed)

        Args:
            kf: KymImage instance that was analyzed.
            success: Whether analysis completed successfully.
        """
        if success:
            self._bus.emit(
                AnalysisCompleted(
                    file=kf,
                    roi_id=roi_id,
                    success=True,
                )
            )
            # This previously triggered MetadataUpdate to refresh UI, but we now
            # emit AnalysisCompleted for analysis-driven refreshes.
            # self._app_state.update_metadata(kf)

    def _on_analysis_cancel(self, e: AnalysisCancel) -> None:
        """Handle analysis cancel intent event.

        Requests cancellation of the current analysis task.

        Args:
            e: AnalysisCancel event (phase="intent").
        """
        if self._task_state.running:
            kf = self._app_state.selected_file
            if kf and kf.path:
                file_stem = Path(kf.path).stem
            else:
                file_stem = "unknown file"
            roi_id = self._app_state.selected_roi_id
            ui.notify(f"Flow analysis canceled for {file_stem} ROI {roi_id}", color="info")
        self._task_state.request_cancel()
