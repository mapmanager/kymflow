"""Stall analysis toolbar view component.

DEPRECATED: Stall analysis is deprecated. This module is kept for reference
but should not be used. The implementation is commented out to prevent usage.

This module provides a view component that displays stall analysis controls
(refactory_bins, min_stall_duration, end_stall_non_nan_bins, and Analyze stalls button).
The view does not emit events directly, but triggers stall analysis which updates
the plot via the existing analysis infrastructure.

This is a duplicate of the stall analysis controls from ImageLineViewerView,
created to be used in the left drawer toolbar without modifying the original.
"""

from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui

# DEPRECATED: Stall analysis is deprecated
# from kymflow.core.analysis.stall_analysis import StallAnalysisParams
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.client_utils import safe_call
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


class StallAnalysisToolbarView:
    """Stall analysis toolbar view component.

    This view displays stall analysis controls with parameter inputs and an
    Analyze stalls button. When the button is clicked, it runs stall analysis
    for the currently selected ROI and triggers a plot update.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by bindings)
        - Stall analysis is triggered by button click

    Attributes:
        _refactory_bins: Refactory bins number input (created in render()).
        _min_duration: Min stall duration number input (created in render()).
        _end_non_nan_bins: End stall non-nan bins number input (created in render()).
        _run_btn: Analyze stalls button (created in render()).
        _current_file: Currently selected file (for running analysis).
        _current_roi_id: Currently selected ROI ID (for running analysis).
        _on_stall_analysis_complete: Optional callback when analysis completes (for plot updates).
    """

    def __init__(self) -> None:
        """Initialize stall analysis toolbar view."""
        # UI components (created in render())
        self._refactory_bins: Optional[ui.number] = None
        self._min_duration: Optional[ui.number] = None
        self._end_non_nan_bins: Optional[ui.number] = None
        self._run_btn: Optional[ui.button] = None

        # State
        self._current_file: Optional[KymImage] = None
        self._current_roi_id: Optional[int] = None
        self._on_stall_analysis_complete: Optional[Callable[[], None]] = None

    def render(self) -> None:
        """Create the stall analysis toolbar UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.
        """
        # Always reset UI element references
        self._refactory_bins = None
        self._min_duration = None
        self._end_non_nan_bins = None
        self._run_btn = None

        # Stall analysis controls (per-ROI, on-demand)
        with ui.row().classes("w-full gap-2 items-center"):
            # ui.label("Stall analysis").classes("text-sm font-semibold")
            self._refactory_bins = ui.number(
                label="refactory_bins",
                value=20,
                min=0,
                step=1,
            ).classes("w-32")
            self._min_duration = ui.number(
                label="min_stall_duration",
                value=2,
                min=1,
                step=1,
            ).classes("w-36")
            self._end_non_nan_bins = ui.number(
                label="end_stall_non_nan_bins",
                value=2,
                min=1,
                step=1,
            ).classes("w-44")
            self._run_btn = ui.button("Analyze stalls", on_click=self._on_analyze_stalls)

    def set_selected_file(self, file: Optional[KymImage]) -> None:
        """Update view for new file selection.

        Called by bindings when FileSelection(phase="state") event is received.

        Args:
            file: Selected KymImage instance, or None if selection cleared.
        """
        safe_call(self._set_selected_file_impl, file)

    def _set_selected_file_impl(self, file: Optional[KymImage]) -> None:
        """Internal implementation of set_selected_file."""
        self._current_file = file
        # Clear ROI when file changes (ROI selection will be updated separately)
        self._current_roi_id = None

    def set_selected_roi(self, roi_id: Optional[int]) -> None:
        """Update view for new ROI selection.

        Called by bindings when ROISelection(phase="state") event is received.

        Args:
            roi_id: Selected ROI ID, or None if selection cleared.
        """
        safe_call(self._set_selected_roi_impl, roi_id)

    def _set_selected_roi_impl(self, roi_id: Optional[int]) -> None:
        """Internal implementation of set_selected_roi."""
        self._current_roi_id = roi_id

    def set_on_stall_analysis_complete(self, callback: Optional[Callable[[], None]]) -> None:
        """Set callback to be called when stall analysis completes.

        This callback can be used to trigger plot updates after analysis.

        Args:
            callback: Callback function to call after analysis completes.
        """
        self._on_stall_analysis_complete = callback

    def _on_analyze_stalls(self) -> None:
        """Run stall analysis for the currently selected ROI, then trigger plot update."""
        kf = self._current_file
        roi_id = self._current_roi_id
        if kf is None:
            ui.notify("Select a file first", color="warning")
            return
        if roi_id is None:
            ui.notify("Select an ROI first", color="warning")
            return
        if (
            self._refactory_bins is None
            or self._min_duration is None
            or self._end_non_nan_bins is None
        ):
            return

        try:
            refactory_bins = int(self._refactory_bins.value)
            min_stall_duration = int(self._min_duration.value)
            end_stall_non_nan_bins = int(self._end_non_nan_bins.value)
        except Exception:
            ui.notify("Invalid stall parameters", color="negative")
            return

        # DEPRECATED: Stall analysis is deprecated
        # params = StallAnalysisParams(
        #     velocity_key="velocity",
        #     refactory_bins=refactory_bins,
        #     min_stall_duration=min_stall_duration,
        #     end_stall_non_nan_bins=end_stall_non_nan_bins,
        # )
        #
        # try:
        #     analysis = kf.get_kym_analysis().run_stall_analysis(roi_id=roi_id, params=params)
        # except Exception as e:
        #     ui.notify(f"Stall analysis failed: {e}", color="negative")
        #     return
        #
        # ui.notify(f"Detected {len(analysis.stalls)} stalls", color="positive")
        
        # DEPRECATED: Stall analysis is deprecated
        ui.notify("Stall analysis is deprecated", color="warning")
        return
        
        # Trigger plot update if callback is set
        if self._on_stall_analysis_complete is not None:
            self._on_stall_analysis_complete()
