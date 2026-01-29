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
from kymflow.gui_v2.events import (
    AddRoi,
    AnalysisCancel,
    AnalysisStart,
    DeleteRoi,
    ROISelection,
    SelectionOrigin,
    SetRoiEditState,
)
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

OnAnalysisStart = Callable[[AnalysisStart], None]
OnAnalysisCancel = Callable[[AnalysisCancel], None]
OnAddRoi = Callable[[AddRoi], None]
OnDeleteRoi = Callable[[DeleteRoi], None]
OnSetRoiEditState = Callable[[SetRoiEditState], None]
OnROISelected = Callable[[ROISelection], None]


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
        on_add_roi: OnAddRoi,
        on_delete_roi: OnDeleteRoi,
        on_set_roi_edit_state: OnSetRoiEditState,
        on_roi_selected: OnROISelected,
    ) -> None:
        """Initialize analysis toolbar view.

        Args:
            on_analysis_start: Callback function that receives AnalysisStart events.
            on_analysis_cancel: Callback function that receives AnalysisCancel events.
            on_add_roi: Callback function that receives AddRoi events.
            on_delete_roi: Callback function that receives DeleteRoi events.
            on_set_roi_edit_state: Callback function that receives SetRoiEditState events.
            on_roi_selected: Callback function that receives ROISelection events.
        """
        self._on_analysis_start = on_analysis_start
        self._on_analysis_cancel = on_analysis_cancel
        self._on_add_roi = on_add_roi
        self._on_delete_roi = on_delete_roi
        self._on_set_roi_edit_state = on_set_roi_edit_state
        self._on_roi_selected = on_roi_selected

        # UI components (created in render())
        self._window_select: Optional[ui.select] = None
        self._start_button: Optional[ui.button] = None
        self._cancel_button: Optional[ui.button] = None
        self._add_roi_button: Optional[ui.button] = None
        self._delete_roi_button: Optional[ui.button] = None
        self._edit_roi_button: Optional[ui.button] = None
        self._roi_select: Optional[ui.select] = None
        self._file_path_label: Optional[ui.label] = None
        self._progress_bar: Optional[ui.linear_progress] = None
        # self._progress_label: Optional[ui.label] = None

        # State
        self._current_file: Optional[KymImage] = None
        self._current_roi_id: Optional[int] = None
        self._task_state: Optional[TaskStateChanged] = None
        self._suppress_roi_emit: bool = False  # Suppress ROI dropdown on_change during programmatic updates

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
        self._start_button = None
        self._cancel_button = None
        self._add_roi_button = None
        self._delete_roi_button = None
        self._edit_roi_button = None
        self._roi_select = None
        self._file_path_label = None
        self._progress_bar = None
        # self._progress_label = None
        # Reset suppression flag to ensure clean state
        self._suppress_roi_emit = False

        # File name label (similar to kym_event_view.py)
        with ui.row().classes("w-full items-center gap-2"):
            ui.label("File").classes("text-sm text-gray-500")
            self._file_path_label = ui.label("No file selected").classes("text-xs text-gray-400")
        
        # ROI management section
        with ui.row().classes("items-end gap-2"):
            # ROI selector dropdown (always visible, disabled when 0 ROIs)
            self._roi_select = ui.select(
                options={},
                label="ROI",
                on_change=self._on_roi_dropdown_change,
            ).classes("min-w-32")
        with ui.row().classes("items-end gap-2"):
            self._add_roi_button = ui.button("Add ROI", on_click=self._on_add_roi_click).props("dense").classes("text-sm")
            self._delete_roi_button = ui.button("Delete ROI", on_click=self._on_delete_roi_click).props("dense").classes("text-sm")
            self._edit_roi_button = ui.button("Edit ROI", on_click=self._on_edit_roi_click).props("dense").classes("text-sm")

        # Analysis controls
        with ui.row().classes("items-end gap-2"):
            # ui.label("Analysis").classes("text-lg font-semibold")
            ui.label("Analysis")
            self._window_select = ui.select(
                options=[16, 32, 64, 128, 256],
                value=16,
                label="Window Points",
            ).classes("w-32")
        with ui.row().classes("items-end gap-2"):
            self._start_button = ui.button("Analyze Flow", on_click=self._on_start_click).props("dense").classes("text-sm")
            self._cancel_button = ui.button("Cancel", on_click=self._on_cancel_click).props("dense").classes("text-sm")

        # Progress bar and label (hidden by default, shown when task is running)
        with ui.column().classes("w-full gap-1"):
            self._progress_bar = ui.linear_progress(value=0.0).props("instant-feedback").classes("w-full")
            # self._progress_label = ui.label("").classes("text-sm text-gray-600")
            # Start hidden, will be shown when task starts
            self._progress_bar.visible = False
            # self._progress_label.visible = False
        
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
        self._update_file_path_label()
        self._update_roi_dropdown()
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
        self._update_roi_dropdown()
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
        
        if self._window_select is not None:
            if running:
                self._window_select.disable()
            else:
                self._window_select.enable()

        if self._roi_select is not None:
            if running:
                self._roi_select.disable()
            else:
                if self._current_file is None:
                    self._roi_select.disable()
                else:
                    num_rois = self._current_file.rois.numRois()
                    if num_rois == 0:
                        self._roi_select.disable()
                    else:
                        self._roi_select.enable()

        # ROI button states
        if self._add_roi_button is not None:
            # Add ROI: enabled when file is selected
            if running:
                self._add_roi_button.disable()
            elif has_file:
                self._add_roi_button.enable()
            else:
                self._add_roi_button.disable()
        
        if self._delete_roi_button is not None:
            # Delete ROI: enabled when file is selected AND ROI is selected
            if running:
                self._delete_roi_button.disable()
            elif has_file and has_roi:
                self._delete_roi_button.enable()
            else:
                self._delete_roi_button.disable()
        
        if self._edit_roi_button is not None:
            # Edit ROI: enabled when file is selected AND ROI is selected
            if running:
                self._edit_roi_button.disable()
            elif has_file and has_roi:
                self._edit_roi_button.enable()
            else:
                self._edit_roi_button.disable()
        
        # Debug logging
        # logger.debug(
        #     f"Update button states: running={running}, cancellable={cancellable}, "
        #     f"has_file={has_file}, has_roi={has_roi}, "
        #     f"task_state={self._task_state is not None}"
        # )

        # Start button: enabled when not running, file selected, and ROI selected
        if running or not has_file or not has_roi:
            self._start_button.disable()
        else:
            self._start_button.enable()

        # Cancel button: enabled only when running and cancellable
        if running and cancellable:
            self._cancel_button.enable()
        else:
            self._cancel_button.disable()
        
        # Update progress bar and label
        # if self._progress_bar is None or self._progress_label is None:
        if self._progress_bar is None:
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
            # self._progress_label.visible = True
            self._progress_bar.value = float(self._task_state.progress)
            # self._progress_label.text = self._task_state.message or ""
        else:
            # Hide when not running and no message
            # logger.debug(f"PROGRESS BAR: Hiding: running={running}, task_state={self._task_state is not None}")
            self._progress_bar.visible = False
            # self._progress_label.visible = False
            self._progress_bar.value = 0.0
            # self._progress_label.text = ""

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

        # Verify file is still valid (safety check)
        if self._current_file is None:
            ui.notify("Select a file first", color="warning")
            return

        # Require ROI selection before starting analysis
        if self._current_roi_id is None:
            ui.notify("Select an ROI first", color="warning")
            return

        # Check for existing analysis on the selected ROI
        try:
            has_analysis = self._current_file.get_kym_analysis().has_analysis(
                self._current_roi_id
            )
        except Exception:
            has_analysis = False

        if has_analysis:
            from pathlib import Path

            file_stem = (
                Path(self._current_file.path).stem
                if self._current_file.path is not None
                else "unknown file"
            )
            roi_id = self._current_roi_id

            with ui.dialog() as dialog, ui.card():
                ui.label("Analysis already exists").classes("text-lg font-semibold")
                ui.label(
                    f"{file_stem} roi {roi_id} already has flow analysis, do you want to proceed"
                ).classes("text-sm")
                with ui.row():
                    ui.button("Cancel", on_click=dialog.close).props("outline")
                    ui.button(
                        "Proceed",
                        on_click=lambda: self._confirm_start_analysis(dialog, window_size),
                    )

            dialog.open()
            return

        self._emit_analysis_start(window_size)

    def _emit_analysis_start(self, window_size: int) -> None:
        """Emit analysis start intent event."""
        self._on_analysis_start(
            AnalysisStart(
                window_size=window_size,
                roi_id=self._current_roi_id,
                phase="intent",
            )
        )

    def _confirm_start_analysis(self, dialog, window_size: int) -> None:
        """Confirm analysis start after warning dialog."""
        dialog.close()
        self._emit_analysis_start(window_size)

    def _on_cancel_click(self) -> None:
        """Handle Cancel button click."""
        # Emit intent event
        self._on_analysis_cancel(
            AnalysisCancel(
                phase="intent",
            )
        )

    def _on_add_roi_click(self) -> None:
        """Handle Add ROI button click."""
        if self._current_file is None:
            return
        
        path_str = str(self._current_file.path) if self._current_file.path else None
        self._on_add_roi(
            AddRoi(
                roi_id=None,
                path=path_str,
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )

    def _on_delete_roi_click(self) -> None:
        """Handle Delete ROI button click."""
        if self._current_file is None or self._current_roi_id is None:
            return
        
        # Check if ROI has analysis or events
        has_analysis = False
        has_events = False
        try:
            kym_analysis = self._current_file.get_kym_analysis()
            if kym_analysis.has_analysis(self._current_roi_id):
                has_analysis = True
            velocity_events = kym_analysis.get_velocity_events(self._current_roi_id)
            if velocity_events and len(velocity_events) > 0:
                has_events = True
        except Exception:
            pass
        
        # Build warning message
        warnings = ["This will delete the ROI"]
        if has_analysis:
            warnings.append("If kym analysis exists for this ROI, it will also be deleted")
        if has_events:
            warnings.append("If kym events exist for this ROI, they will also be deleted")
        
        warning_text = "\n".join(f"• {w}" for w in warnings)
        
        # Show confirmation dialog
        with ui.dialog() as dialog, ui.card():
            ui.label("Delete ROI?").classes("text-lg font-semibold")
            ui.label(warning_text).classes("text-sm")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("outline")
                ui.button("Delete", on_click=lambda: self._confirm_delete_roi(dialog)).props("color=red")
        
        dialog.open()

    def _confirm_delete_roi(self, dialog) -> None:
        """Confirm deletion and emit DeleteRoi event."""
        dialog.close()
        
        if self._current_file is None or self._current_roi_id is None:
            return
        
        path_str = str(self._current_file.path) if self._current_file.path else None
        self._on_delete_roi(
            DeleteRoi(
                roi_id=self._current_roi_id,
                path=path_str,
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )

    def _on_edit_roi_click(self) -> None:
        """Handle Edit ROI button click."""
        if self._current_file is None or self._current_roi_id is None:
            return
        
        path_str = str(self._current_file.path) if self._current_file.path else None
        self._on_set_roi_edit_state(
            SetRoiEditState(
                enabled=True,
                roi_id=self._current_roi_id,
                path=path_str,
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )

    def _update_roi_dropdown(self) -> None:
        """Update ROI dropdown options based on current file.
        
        Always shows the dropdown (disabled when 0 ROIs, enabled when >=1 ROIs).
        """
        if self._roi_select is None:
            return

        kf = self._current_file
        if kf is None:
            # No file selected, clear options and disable
            self._suppress_roi_emit = True
            try:
                self._roi_select.set_options({}, value=None)
                self._roi_select.disable()
            finally:
                self._suppress_roi_emit = False
            return

        # Use RoiSet.get_roi_ids() public API
        roi_ids = kf.rois.get_roi_ids()
        options = {roi_id: f"ROI {roi_id}" for roi_id in roi_ids}
        
        # Suppress on_change callback during programmatic update to prevent feedback loop
        self._suppress_roi_emit = True
        try:
            if self._current_roi_id is not None and self._current_roi_id in roi_ids:
                self._roi_select.set_options(options, value=self._current_roi_id)
            else:
                # Current ROI is invalid or None, set options without value
                self._roi_select.set_options(options, value=None)
        finally:
            self._suppress_roi_emit = False
        
        # Enable/disable based on number of ROIs
        num_rois = kf.rois.numRois()
        if num_rois == 0:
            self._roi_select.disable()
        else:
            self._roi_select.enable()

    def _on_roi_dropdown_change(self) -> None:
        """Handle ROI dropdown selection change."""
        if self._roi_select is None:
            return
        # Suppress events during programmatic updates to prevent feedback loop
        if self._suppress_roi_emit:
            return
        roi_id = self._roi_select.value
        # Emit intent event with ANALYSIS_TOOLBAR origin
        self._on_roi_selected(
            ROISelection(
                roi_id=roi_id,
                origin=SelectionOrigin.ANALYSIS_TOOLBAR,
                phase="intent",
            )
        )

    def _update_file_path_label(self) -> None:
        """Update the file path label with current file name (stem) or placeholder."""
        if self._file_path_label is None:
            return
        if self._current_file and self._current_file.path:
            try:
                from pathlib import Path
                file_name = Path(self._current_file.path).stem
                self._file_path_label.text = file_name
            except (ValueError, TypeError):
                self._file_path_label.text = "No file selected"
        else:
            self._file_path_label.text = "No file selected"
