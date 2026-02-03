"""Controller for handling event detection events from the UI.

This module provides a controller that translates user event detection intents
(DetectEvents phase="intent") into synchronous velocity event analysis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import DetectEvents
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class EventAnalysisController:
    """Apply event detection intents to synchronous analysis execution.

    This controller handles event detection intent events from the UI (typically
    from the analysis toolbar) and runs velocity event detection synchronously.

    Update Flow:
        1. User clicks "Detect Events" → AnalysisToolbarView emits DetectEvents(phase="intent")
        2. This controller receives event → calls run_velocity_event_analysis()
        3. Analysis runs synchronously (fast, no progress tracking)
        4. Controller emits DetectEvents(phase="state") → KymEventBindings refreshes table

    Attributes:
        _app_state: AppState instance to access selected file.
        _bus: EventBus instance for emitting state events.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize event analysis controller.

        Subscribes to DetectEvents (phase="intent") events from the bus.

        Args:
            app_state: AppState instance to access selected file.
            bus: EventBus instance to subscribe to and emit events.
        """
        self._app_state: AppState = app_state
        self._bus: EventBus = bus
        bus.subscribe_intent(DetectEvents, self._on_detect_events)

    def _on_detect_events(self, e: DetectEvents) -> None:
        """Handle event detection intent event.

        Runs velocity event detection synchronously on the currently selected file
        or all files in AcqImageList, depending on the all_files flag.

        Args:
            e: DetectEvents event (phase="intent") containing roi_id and parameters.
        """
        # Handle all-files mode
        if e.all_files:
            # Verify app_state.files exists (do NOT check if it has images)
            if self._app_state.files is None:
                ui.notify("No folder loaded", color="warning")
                return

            # Log for debugging
            # logger.info(
            #     "Starting event detection for all files: int_param=%s, float_param=%s, text_param=%s",
            #     e.int_param,
            #     e.float_param,
            #     e.text_param,
            # )

            try:
                # Call detect_all_events() on AcqImageList
                # This method handles empty lists and images without kym_analysis gracefully
                self._app_state.files.detect_all_events(
                    baseline_drop_params=e.baseline_drop_params,
                    nan_gap_params=e.nan_gap_params,
                    zero_gap_params=e.zero_gap_params,
                )
                
                # Get total number of events across all files
                total_events = self._app_state.files.total_number_of_event()
                
                logger.info(
                    "Event detection completed for all files: total_events=%d",
                    total_events,
                )

                # Emit state event to trigger UI refresh
                self._bus.emit(
                    DetectEvents(
                        roi_id=None,
                        path=None,
                        all_files=True,
                        # int_param=e.int_param,
                        # float_param=e.float_param,
                        # text_param=e.text_param,
                        phase="state",
                    )
                )

                ui.notify(
                    f"Detected events for all files (total: {total_events} events)",
                    color="positive",
                )

            except Exception as exc:
                logger.exception("Unexpected error during all-files event detection")
                ui.notify(f"Unexpected error: {exc}", color="negative")
            return

        # Single-file mode (existing behavior)
        kf = self._app_state.selected_file
        if not kf:
            ui.notify("Select a file first", color="warning")
            return

        # Require ROI selection before starting detection
        if e.roi_id is None:
            ui.notify("ROI selection required", color="warning")
            return

        # Verify ROI exists in the selected file
        roi_ids = kf.rois.get_roi_ids()
        if e.roi_id not in roi_ids:
            logger.warning(
                "DetectEvents: ROI %s not found in file %s (available: %s)",
                e.roi_id,
                kf.path,
                roi_ids,
            )
            ui.notify(f"ROI {e.roi_id} not found in selected file", color="warning")
            return

        # Log for debugging
        # logger.info(
        #     "Starting event detection: file=%s, roi_id=%s, int_param=%s, float_param=%s, text_param=%s",
        #     kf.path,
        #     e.roi_id,
        #     e.int_param,
        #     e.float_param,
        #     e.text_param,
        # )

        try:
            # Run velocity event analysis synchronously
            kym_analysis = kf.get_kym_analysis()
            events = kym_analysis.run_velocity_event_analysis(
                roi_id=e.roi_id,
                remove_outliers=True,
                baseline_drop_params=e.baseline_drop_params,
                nan_gap_params=e.nan_gap_params,
                zero_gap_params=e.zero_gap_params,
            )
            
            logger.info(
                "Event detection completed: file=%s, roi_id=%s, events_detected=%d",
                kf.path,
                e.roi_id,
                len(events),
            )

            # Emit state event to trigger UI refresh
            path_str = str(kf.path) if kf.path else None
            self._bus.emit(
                DetectEvents(
                    roi_id=e.roi_id,
                    path=path_str,
                    all_files=False,
                    # int_param=e.int_param,
                    # float_param=e.float_param,
                    # text_param=e.text_param,
                    phase="state",
                )
            )

            ui.notify(
                f"Detected {len(events)} events for ROI {e.roi_id}",
                color="positive",
            )

        except ValueError as exc:
            logger.warning("Event detection failed: %s", exc)
            ui.notify(f"Event detection failed: {exc}", color="negative")
        except Exception as exc:
            logger.exception("Unexpected error during event detection")
            ui.notify(f"Unexpected error: {exc}", color="negative")
