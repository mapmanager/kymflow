"""Analysis toolbar view component.

This module provides a view component that displays analysis controls (window
size selector, Analyze Flow button, Cancel button). The view emits
AnalysisStart(phase="intent") and AnalysisCancel(phase="intent") events when
users interact with controls, but does not subscribe to events (that's handled
by AnalysisToolbarBindings).
"""

from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import AnalysisCancel, AnalysisStart
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

OnAnalysisStart = Callable[[AnalysisStart], None]
OnAnalysisCancel = Callable[[AnalysisCancel], None]


class AnalysisToolbarView:
    """Analysis toolbar view component.

    This view displays analysis controls with window size selector, Analyze Flow
    button, and Cancel button. Users can select window size and start/cancel
    analysis, which triggers AnalysisStart or AnalysisCancel intent events.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by bindings)
        - Events emitted via callbacks

    Attributes:
        _on_analysis_start: Callback function that receives AnalysisStart events.
        _on_analysis_cancel: Callback function that receives AnalysisCancel events.
        _window_select: Window size selector dropdown (created in render()).
        _start_button: Analyze Flow button (created in render()).
        _cancel_button: Cancel button (created in render()).
        _current_file: Currently selected file (for enabling/disabling buttons).
        _task_state: Current task state (for button states).
    """

    def __init__(
        self,
        *,
        on_analysis_start: OnAnalysisStart,
        on_analysis_cancel: OnAnalysisCancel,
    ) -> None:
        """Initialize analysis toolbar view.

        Args:
            on_analysis_start: Callback function that receives AnalysisStart events.
            on_analysis_cancel: Callback function that receives AnalysisCancel events.
        """
        self._on_analysis_start = on_analysis_start
        self._on_analysis_cancel = on_analysis_cancel

        # UI components (created in render())
        self._window_select: Optional[ui.select] = None
        self._start_button: Optional[ui.button] = None
        self._cancel_button: Optional[ui.button] = None
        self._progress_bar: Optional[ui.linear_progress] = None
        self._progress_label: Optional[ui.label] = None

        # State
        self._current_file: Optional[KymImage] = None
        self._current_roi_id: Optional[int] = None
        self._task_state: Optional[TaskStateChanged] = None

    def render(self) -> None:
        """Create the analysis toolbar UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.

        Attributes:
            _window_select: Dropdown for selecting analysis window size.
        """
        # Always reset UI element references
        
        self._window_select: Optional[ui.select] = None
        
        # Analyze Flow button
        self._start_button = None
        
        # Cancel button
        self._cancel_button = None
        
        # Progress bar
        self._progress_bar = None
        self._progress_label = None

        with ui.row().classes("items-end gap-2"):
            ui.label("Analysis").classes("text-lg font-semibold")
            self._window_select = ui.select(
                options=[16, 32, 64, 128, 256],
                value=16,
                label="Window Points",
            ).classes("w-32")
            self._start_button = ui.button("Analyze Flow", on_click=self._on_start_click)
            self._cancel_button = ui.button("Cancel", on_click=self._on_cancel_click)
        
        # Progress bar and label (hidden by default, shown when task is running)
        with ui.column().classes("w-full gap-1"):
            self._progress_bar = ui.linear_progress(value=0.0).props("instant-feedback").classes("w-full")
            self._progress_label = ui.label("").classes("text-sm text-gray-600")
            # Start hidden, will be shown when task starts
            self._progress_bar.visible = False
            self._progress_label.visible = False

        # Initialize button states
        self._update_button_states()

    def set_selected_file(self, file: Optional[KymImage]) -> None:
        """Update view for new file selection.

        Called by bindings when FileSelection(phase="state") event is received.
        Enables/disables buttons based on file selection.

        Args:
            file: Selected KymImage instance, or None if selection cleared.
        """
        safe_call(self._set_selected_file_impl, file)

    def _set_selected_file_impl(self, file: Optional[KymImage]) -> None:
        """Internal implementation of set_selected_file."""
        self._current_file = file
        # Reset ROI when file changes (ROI selection will be updated separately)
        self._current_roi_id = None
        self._update_button_states()
    
    def set_selected_roi(self, roi_id: Optional[int]) -> None:
        """Update view for new ROI selection.

        Called by bindings when ROISelection(phase="state") event is received.
        Updates ROI selection and button states.

        Args:
            roi_id: Selected ROI ID, or None if selection cleared.
        """
        safe_call(self._set_selected_roi_impl, roi_id)
    
    def _set_selected_roi_impl(self, roi_id: Optional[int]) -> None:
        """Internal implementation of set_selected_roi."""
        self._current_roi_id = roi_id
        self._update_button_states()

    def set_task_state(self, task_state: TaskStateChanged) -> None:
        """Update view for task state changes.

        Called by bindings when TaskStateChanged event is received.
        Updates button states based on task running/cancellable state.

        Args:
            task_state: Current task state.
        """
        safe_call(self._set_task_state_impl, task_state)

    def _set_task_state_impl(self, task_state: TaskStateChanged) -> None:
        """Internal implementation of set_task_state."""
        # logger.debug(
        #     f"set_task_state_impl: running={task_state.running}, "
        #     f"cancellable={task_state.cancellable}, progress={task_state.progress}"
        # )
        self._task_state = task_state
        self._update_button_states()

    def _update_button_states(self) -> None:
        """Update button states based on current file, ROI selection, and task state."""
        if self._start_button is None or self._cancel_button is None:
            return

        running = self._task_state.running if self._task_state else False
        cancellable = self._task_state.cancellable if self._task_state else False
        has_file = self._current_file is not None
        has_roi = self._current_roi_id is not None
        
        # Debug logging
        # logger.debug(
        #     f"Update button states: running={running}, cancellable={cancellable}, "
        #     f"has_file={has_file}, has_roi={has_roi}, "
        #     f"task_state={self._task_state is not None}"
        # )

        # Start button: enabled when not running, file selected, and ROI selected
        if running or not has_file or not has_roi:
            self._start_button.disable()
            if running:
                self._start_button.props("color=red")
            else:
                self._start_button.props(remove="color")
        else:
            self._start_button.enable()
            self._start_button.props(remove="color")

        # Cancel button: enabled only when running and cancellable
        if running and cancellable:
            self._cancel_button.enable()
            self._cancel_button.props("color=red")
        else:
            self._cancel_button.disable()
            self._cancel_button.props(remove="color")
        
        # Update progress bar and label
        if self._progress_bar is None or self._progress_label is None:
            # logger.warning(f"Progress bar or label is None! progress_bar={self._progress_bar}, progress_label={self._progress_label}")
            return
        
        # Show progress bar when running OR when there's a message with progress
        should_show = False
        if running and self._task_state is not None:
            # Show progress bar when running
            should_show = True
            # logger.info(f"PROGRESS BAR: Showing (running): progress={self._task_state.progress:.2%}, message={self._task_state.message}")
        elif self._task_state is not None and self._task_state.message and self._task_state.progress > 0:
            # Show briefly after completion to show final status
            should_show = True
            # logger.info(f"PROGRESS BAR: Showing (completed): progress={self._task_state.progress:.2%}, message={self._task_state.message}")
        
        if should_show:
            self._progress_bar.visible = True
            self._progress_label.visible = True
            self._progress_bar.value = float(self._task_state.progress)
            self._progress_label.text = self._task_state.message or ""
        else:
            # Hide when not running and no message
            # logger.debug(f"PROGRESS BAR: Hiding: running={running}, task_state={self._task_state is not None}")
            self._progress_bar.visible = False
            self._progress_label.visible = False
            self._progress_bar.value = 0.0
            self._progress_label.text = ""

    def _on_start_click(self) -> None:
        """Handle Analyze Flow button click."""
        if self._window_select is None:
            return

        window_value = self._window_select.value
        if window_value is None:
            return

        try:
            window_size = int(window_value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid window size: {window_value}, expectin an int")
            return

        # Require ROI selection before starting analysis
        if self._current_roi_id is None:
            from nicegui import ui
            ui.notify("Select an ROI first", color="warning")
            return

        # Emit intent event with selected ROI ID
        self._on_analysis_start(
            AnalysisStart(
                window_size=window_size,
                roi_id=self._current_roi_id,
                phase="intent",
            )
        )

    def _on_cancel_click(self) -> None:
        """Handle Cancel button click."""
        # Emit intent event
        self._on_analysis_cancel(
            AnalysisCancel(
                phase="intent",
            )
        )
