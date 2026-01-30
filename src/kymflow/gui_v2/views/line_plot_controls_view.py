"""Line plot controls view component.

This module provides a view component that displays line plot filter controls
(remove outliers checkbox, median filter checkbox, and full zoom button).
The view emits callbacks when users interact with controls, but does not
subscribe to events (that's handled by LinePlotControlsBindings).

This is a duplicate of the line plot controls from ImageLineViewerView,
created to be used in the left drawer toolbar without modifying the original.
"""

from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui

from kymflow.gui_v2.client_utils import safe_call
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

OnFilterChange = Callable[[bool, bool], None]  # (remove_outliers, median_filter)
OnFullZoom = Callable[[], None]


class LinePlotControlsView:
    """Line plot controls view component.

    This view displays filter controls and zoom button for the line plot.
    Users can toggle filters and reset zoom, which triggers callbacks.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by bindings)
        - Events emitted via callbacks

    Attributes:
        _on_filter_change: Callback function that receives filter state changes.
        _on_full_zoom: Callback function that receives full zoom requests.
        _remove_outliers_cb: Remove outliers (flowanalysis) checkbox (created in render()).
        _median_filter_cb: Median filter checkbox (created in render()).
        _full_zoom_btn: Full zoom button (created in render()).
        _current_file: Currently selected file (for enabling/disabling controls).
        _current_roi_id: Currently selected ROI ID (for enabling/disabling controls).
    """

    def __init__(
        self,
        *,
        on_filter_change: OnFilterChange,
        on_full_zoom: OnFullZoom,
    ) -> None:
        """Initialize line plot controls view.

        Args:
            on_filter_change: Callback function that receives filter state changes.
            on_full_zoom: Callback function that receives full zoom requests.
        """
        self._on_filter_change = on_filter_change
        self._on_full_zoom = on_full_zoom

        # UI components (created in render())
        self._remove_outliers_cb: Optional[ui.checkbox] = None
        self._median_filter_cb: Optional[ui.checkbox] = None
        self._full_zoom_btn: Optional[ui.button] = None

        # State (for enabling/disabling controls)
        self._current_file = None
        self._current_roi_id: Optional[int] = None

    def render(self) -> None:
        """Create the line plot controls UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.
        """
        # Always reset UI element references
        self._remove_outliers_cb = None
        self._median_filter_cb = None
        self._full_zoom_btn = None

        # Filter checkboxes and zoom button
        with ui.row().classes("w-full gap-2 items-center"):
            self._remove_outliers_cb = ui.checkbox("Remove outliers (flowanalysis)")
            self._remove_outliers_cb.on("update:model-value", self._on_filter_change_handler)
            
        with ui.row().classes("w-full gap-2 items-center"):
            self._median_filter_cb = ui.checkbox("Median filter")
            self._median_filter_cb.on("update:model-value", self._on_filter_change_handler)
            
        with ui.row().classes("w-full gap-2 items-center"):
            self._full_zoom_btn = ui.button("Full zoom", icon="zoom_out_map").props("dense").classes("text-sm")
            self._full_zoom_btn.on("click", self._on_full_zoom_handler)

        # Initialize button states
        self._update_control_states()

    def set_selected_file(self, file) -> None:
        """Update view for new file selection.

        Called by bindings when FileSelection(phase="state") event is received.
        Enables/disables controls based on file selection.

        Args:
            file: Selected file instance, or None if selection cleared.
        """
        safe_call(self._set_selected_file_impl, file)

    def _set_selected_file_impl(self, file) -> None:
        """Internal implementation of set_selected_file."""
        self._current_file = file
        # Clear ROI when file changes (ROI selection will be updated separately)
        self._current_roi_id = None
        self._update_control_states()

    def set_selected_roi(self, roi_id: Optional[int]) -> None:
        """Update view for new ROI selection.

        Called by bindings when ROISelection(phase="state") event is received.
        Enables/disables controls based on ROI selection.

        Args:
            roi_id: Selected ROI ID, or None if selection cleared.
        """
        safe_call(self._set_selected_roi_impl, roi_id)

    def _set_selected_roi_impl(self, roi_id: Optional[int]) -> None:
        """Internal implementation of set_selected_roi."""
        self._current_roi_id = roi_id
        self._update_control_states()

    def _update_control_states(self) -> None:
        """Update control states based on current file and ROI selection."""
        if self._remove_outliers_cb is None or self._median_filter_cb is None or self._full_zoom_btn is None:
            return

        has_file = self._current_file is not None
        has_roi = self._current_roi_id is not None

        # Enable controls when both file and ROI are selected
        if has_file and has_roi:
            self._remove_outliers_cb.enable()
            self._median_filter_cb.enable()
            self._full_zoom_btn.enable()
        else:
            self._remove_outliers_cb.disable()
            self._median_filter_cb.disable()
            self._full_zoom_btn.disable()

    def _on_filter_change_handler(self) -> None:
        """Handle filter checkbox changes."""
        if self._remove_outliers_cb is None or self._median_filter_cb is None:
            return

        remove_outliers = self._remove_outliers_cb.value
        median_filter = self._median_filter_cb.value

        # Emit callback with current filter values
        self._on_filter_change(remove_outliers, median_filter)

    def _on_full_zoom_handler(self) -> None:
        """Handle full zoom button click."""
        # Emit callback
        self._on_full_zoom()
