"""Analysis toolbar view component.

This module provides a view component that displays analysis controls (window
size selector, Analyze Flow button, Cancel button). The view emits
AnalysisStart(phase="intent") and AnalysisCancel(phase="intent") events when
users interact with controls, but does not subscribe to events (that's handled
by AnalysisToolbarBindings).
"""

from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from nicegui import app, ui
from nicewidgets.utils.clipboard import copy_to_clipboard

from kymflow.core.image_loaders.kym_image import KymImage

if TYPE_CHECKING:
    from kymflow.gui_v2.app_context import AppContext
from kymflow.core.analysis.velocity_events.velocity_events import (
    BaselineDropParams,
    NanGapParams,
    ZeroGapParams,
)
from kymflow.gui_v2._pywebview import _prompt_for_save_path
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import (
    AddRoi,
    AnalysisCancel,
    AnalysisStart,
    DetectEvents,
)
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.styles import kym_expansion

logger = get_logger(__name__)

OnAnalysisStart = Callable[[AnalysisStart], None]
OnAnalysisCancel = Callable[[AnalysisCancel], None]
OnAddRoi = Callable[[AddRoi], None]
OnDetectEvents = Callable[[DetectEvents], None]
OnBatchKymEvent = Callable[[], None]
OnBatchRadon = Callable[[], None]


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
        _app_context: AppContext for accessing app configuration.
    """

    def __init__(
        self,
        *,
        app_context: "AppContext",
        on_analysis_start: OnAnalysisStart,
        on_analysis_cancel: OnAnalysisCancel,
        on_add_roi: OnAddRoi | None = None,
        on_detect_events: OnDetectEvents,
        on_batch_kym_event: OnBatchKymEvent | None = None,
        on_batch_radon: OnBatchRadon | None = None,
    ) -> None:
        """Initialize analysis toolbar view.

        Args:
            app_context: AppContext for accessing app configuration.
            on_analysis_start: Callback function that receives AnalysisStart events.
            on_analysis_cancel: Callback function that receives AnalysisCancel events.
            on_add_roi: Callback function that receives AddRoi events.
            on_detect_events: Callback function that receives DetectEvents events.
            on_batch_kym_event: Optional callback to open batch kym-event analysis.
            on_batch_radon: Optional callback to open batch Radon analysis.
        """
        self._app_context = app_context
        self._on_analysis_start = on_analysis_start
        self._on_analysis_cancel = on_analysis_cancel
        self._on_add_roi = on_add_roi
        self._on_detect_events = on_detect_events
        self._on_batch_kym_event = on_batch_kym_event
        self._on_batch_radon = on_batch_radon

        # UI components (created in render())
        self._window_select: Optional[ui.select] = None
        self._start_button: Optional[ui.button] = None
        self._cancel_button: Optional[ui.button] = None
        self._progress_bar: Optional[ui.linear_progress] = None
        # self._progress_label: Optional[ui.label] = None
        self._detect_events_button: Optional[ui.button] = None
        self._reset_event_params_button: Optional[ui.button] = None
        self._copy_event_results_button: Optional[ui.button] = None
        self._save_event_results_button: Optional[ui.button] = None
        # self._detect_all_events_button: Optional[ui.button] = None  # Commented out: Detect Events (all files) disabled
        self._win_cmp_sec_input: Optional[ui.number] = None
        self._smooth_sec_input: Optional[ui.number] = None
        self._mad_k_input: Optional[ui.number] = None
        self._abs_score_floor_input: Optional[ui.number] = None
        self._batch_kym_event_button: Optional[ui.button] = None
        self._batch_radon_button: Optional[ui.button] = None

        # State
        self._current_file: Optional[KymImage] = None
        self._current_channel: Optional[int] = None
        self._current_roi_id: Optional[int] = None
        self._task_state: Optional[TaskStateChanged] = None
        self._batch_task_state: Optional[TaskStateChanged] = None

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
        self._progress_bar = None
        # self._progress_label = None
        self._detect_events_button = None
        self._reset_event_params_button = None
        self._copy_event_results_button = None
        self._save_event_results_button = None
        # self._detect_all_events_button = None  # Commented out: Detect Events (all files) disabled
        self._win_cmp_sec_input = None
        self._smooth_sec_input = None
        self._mad_k_input = None
        self._abs_score_floor_input = None
        self._batch_kym_event_button = None
        self._batch_radon_button = None

        self._render_flow_analysis_widget()
        
        # Event Analysis widget (modular, self-contained)
        self._render_event_analysis_widget()
        
        # Initialize button states
        self._update_button_states()

    def _render_flow_analysis_widget(self) -> None:
        """Render the Flow Analysis widget (modular, self-contained).

        Creates UI elements for flow analysis: action buttons, progress bar, and
        window-size selector. This method intentionally preserves the existing
        layout and behavior.
        """
        with kym_expansion("Flow Analysis", value=True).classes("w-full"):
            with ui.column().classes("w-full gap-2"):
                # Analyze Flow and Cancel buttons (moved to top)
                with ui.row().classes("items-end gap-2"):
                    self._start_button = ui.button("Analyze Flow", on_click=self._on_start_click).props("dense").classes("text-sm")
                    self._cancel_button = ui.button("Cancel", on_click=self._on_cancel_click).props("dense").classes("text-sm")
                    if self._on_batch_radon is not None:
                        self._batch_radon_button = ui.button(
                            "Batch Analyze",
                            on_click=self._on_batch_radon_click,
                        ).props("dense").classes("text-sm")

                # Progress bar and label (hidden by default, shown when task is running)
                with ui.column().classes("w-full gap-1"):
                    self._progress_bar = ui.linear_progress(value=0.0).props("instant-feedback").classes("w-full")
                    # self._progress_label = ui.label("").classes("text-sm text-gray-600")
                    # Start hidden, will be shown when task starts
                    self._progress_bar.visible = False
                    # self._progress_label.visible = False

                # Analysis controls - Window Points select (moved below buttons and progress bar)
                with ui.row().classes("items-end gap-2"):
                    self._window_select = ui.select(
                        options=[16, 32, 64, 128, 256],
                        value=16,
                        label="Window Points",
                    ).classes("w-32")

    def set_selected_file(
        self,
        file: Optional[KymImage],
        channel: Optional[int],
        roi_id: Optional[int],
    ) -> None:
        """Update view for new file selection.

        Called by bindings when FileSelection(phase="state") event is received.
        Sets full selection state (file, channel, roi_id) and updates UI.

        Args:
            file: Selected KymImage instance, or None if selection cleared.
            channel: 1-based channel index, or None (e.g. no channels).
            roi_id: Selected ROI id, or None if file has no ROIs.
        """
        safe_call(self._set_selected_file_impl, file, channel, roi_id)

    def _set_selected_file_impl(
        self,
        file: Optional[KymImage],
        channel: Optional[int],
        roi_id: Optional[int],
    ) -> None:
        """Internal implementation of set_selected_file."""
        self._current_file = file
        self._current_channel = channel
        self._current_roi_id = roi_id
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
        """Update view for home task state changes.

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

    def set_batch_task_state(self, task_state: TaskStateChanged) -> None:
        """Update view for batch or batch-overall task state (disables controls while batch runs).

        Args:
            task_state: Task state for ``task_type`` ``batch`` or ``batch_overall``.
        """
        safe_call(self._set_batch_task_state_impl, task_state)

    def _set_batch_task_state_impl(self, task_state: TaskStateChanged) -> None:
        """Apply batch task state for toolbar chrome."""
        self._batch_task_state = task_state
        self._update_button_states()

    def _update_button_states(self) -> None:
        """Update button states based on current file, ROI selection, and task state."""
        if self._start_button is None or self._cancel_button is None:
            return

        home_running = self._task_state.running if self._task_state else False
        batch_running = self._batch_task_state.running if self._batch_task_state else False
        running = home_running or batch_running
        if home_running and self._task_state is not None:
            cancellable = self._task_state.cancellable
        elif batch_running and self._batch_task_state is not None:
            cancellable = self._batch_task_state.cancellable
        else:
            cancellable = False
        has_file = self._current_file is not None
        has_roi = self._current_roi_id is not None
        
        if self._window_select is not None:
            if running:
                self._window_select.disable()
            else:
                self._window_select.enable()

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
        
        # Detect Events button: enabled when file and ROI are selected (no dependency on task state)
        if self._detect_events_button is not None:
            if has_file and has_roi:
                self._detect_events_button.enable()
            else:
                self._detect_events_button.disable()

        has_files_loaded = len(self._app_context.app_state.files) > 0
        can_save_to_file = self._app_context.runtime_env.has_file_system_access
        if self._copy_event_results_button is not None:
            if running or not has_files_loaded:
                self._copy_event_results_button.disable()
            else:
                self._copy_event_results_button.enable()
        if self._save_event_results_button is not None:
            if running or not has_files_loaded or not can_save_to_file:
                self._save_event_results_button.disable()
            else:
                self._save_event_results_button.enable()

        if self._batch_kym_event_button is not None:
            if running or not has_files_loaded:
                self._batch_kym_event_button.disable()
            else:
                self._batch_kym_event_button.enable()
        if self._batch_radon_button is not None:
            if running or not has_files_loaded:
                self._batch_radon_button.disable()
            else:
                self._batch_radon_button.enable()
        
        # Detect Events (all files) button: enabled when not running a task
        # (Controller will validate that files exist)
        # Commented out: Detect Events (all files) disabled
        # if self._detect_all_events_button is not None:
        #     if running:
        #         self._detect_all_events_button.disable()
        #     else:
        #         self._detect_all_events_button.enable()
        
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
        
        # if never taken
        if self._window_select is None:
            return

        window_value = self._window_select.value
        # if never taken
        if window_value is None:
            return

        # window value can always be cast int()
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
        # Require channel selection before starting analysis
        if self._current_channel is None:
            ui.notify("Select a channel first", color="warning")
            return

        # Check for existing analysis on the selected ROI and channel
        ka = self._current_file.get_kym_analysis()
        radon = ka.get_analysis_object("RadonAnalysis")
        try:
            has_analysis = radon.has_analysis(self._current_roi_id, self._current_channel) if radon else False
        except Exception:
            has_analysis = False

        if has_analysis:

            file_stem = (
                Path(self._current_file.path).stem
                if self._current_file.path is not None
                else "unknown file"
            )
            roi_id = self._current_roi_id
            channel = self._current_channel

            # check if we have v0 flow analysis and do not allow analysis
            radon = self._current_file.get_kym_analysis().get_analysis_object("RadonAnalysis")
            if radon is not None and radon.has_v0_flow_analysis(roi_id, channel):
                # raise ValueError(f"ROI {roi_id} already has v0 analysis, cannot run new analysis")
                logger.warning(f"ROI {roi_id} already has v0 analysis, cannot run new analysis")
                
                
                with ui.dialog() as dialog, ui.card():
                    ui.label("Not allowed to analyze flow").classes("text-lg font-semibold")
                    ui.label(
                        f"{file_stem} roi {roi_id} already has v0 flow analysis"
                    ).classes("text-sm")
                    with ui.row():
                        ui.button("OK", on_click=dialog.close).props("outline")
                        # ui.button(
                        #     "Proceed",
                        #     on_click=lambda: self._confirm_start_analysis(dialog, window_size),
                        # )

                dialog.open()
                return

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
                channel=self._current_channel,
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

    def _render_event_analysis_widget(self) -> None:
        """Render the Event Analysis widget (modular, self-contained).
        
        Creates UI elements for event detection: label, parameter inputs, and button.
        This method is self-contained and creates all UI elements in a single block.
        """
        ui.label("Event Analysis").classes("text-sm font-semibold")
        with ui.card().classes("w-full"):
            with ui.column().classes("w-full gap-2"):
                with ui.row().classes("items-end gap-2"):
                    self._detect_events_button = ui.button(
                        "Detect Events",
                        on_click=self._on_detect_events_click,
                    )
                    self._reset_event_params_button = ui.button(
                        "Reset",
                        on_click=self._on_reset_event_params_click,
                    )
                    if self._on_batch_kym_event is not None:
                        self._batch_kym_event_button = ui.button(
                            "Batch Analyze",
                            on_click=self._on_batch_kym_event_click,
                        ).props("dense").classes("text-sm")

                with ui.row().classes("items-end gap-2"):
                    self._copy_event_results_button = ui.button(
                        "Copy Results",
                        on_click=self._on_copy_event_results_click,
                    ).props("dense").classes("text-sm")
                    self._save_event_results_button = ui.button(
                        "Save Results",
                        on_click=lambda: asyncio.create_task(self._on_save_event_results_click()),
                    ).props("dense").classes("text-sm")

                self._win_cmp_sec_input = ui.number(
                    label="win_cmp_sec",
                    value=BaselineDropParams().win_cmp_sec,
                    format="%.2f",
                    min=0.01,
                    step=0.01
                ).classes("w-full").props("dense")

                self._smooth_sec_input = ui.number(
                    label="smooth_sec",
                    value=BaselineDropParams().smooth_sec,
                    format="%.2f",
                    min=0.01,
                    step=0.01
                ).classes("w-full").props("dense")

                self._mad_k_input = ui.number(
                    label="mad_k",
                    value=BaselineDropParams().mad_k,
                    format="%.2f",
                    min=0.1,
                    step=0.1
                ).classes("w-full").props("dense")

                self._abs_score_floor_input = ui.number(
                    label="abs_score_floor",
                    value=BaselineDropParams().abs_score_floor,
                    format="%.2f",
                    min=0.0,
                    step=0.01
                ).classes("w-full").props("dense")

    def _get_velocity_event_csv_text(self) -> str:
        """Return velocity event cache as TSV text for copy/save operations.

        Returns:
            Tab-separated text with header row, or empty string if unavailable.
        """
        files = self._app_context.app_state.files
        if len(files) == 0:
            return ""
        df = files.get_velocity_event_df()
        if df is None or df.empty:
            return ""
        return df.to_csv(index=False, sep="\t")

    def _on_copy_event_results_click(self) -> None:
        """Copy velocity-event cache results to clipboard."""
        text = self._get_velocity_event_csv_text()
        if not text:
            ui.notify("No kym event results to copy", type="warning")
            return
        copy_to_clipboard(text)
        ui.notify("Kym event report copied to clipboard", type="positive")

    async def _on_save_event_results_click(self) -> None:
        """Save velocity-event cache to a user-selected CSV path."""
        if not self._app_context.runtime_env.has_file_system_access:
            ui.notify("Saving requires native mode file access", type="warning")
            return
        if getattr(app, "native", None) is None:
            ui.notify("Native save dialog not available", type="warning")
            return
        files = self._app_context.app_state.files
        if len(files) == 0:
            ui.notify("No files loaded", type="warning")
            return
        df = files.get_velocity_event_df()
        if df is None or df.empty:
            ui.notify("No kym event results to save", type="warning")
            return

        selected_path = await _prompt_for_save_path(
            initial=Path.home(),
            suggested_filename="kym_event_db.csv",
            file_extension=".csv",
        )
        if not selected_path:
            return
        try:
            df.to_csv(selected_path, index=False)
            ui.notify(f"Saved kym event results to {Path(selected_path).name}", type="positive")
        except Exception as exc:
            logger.exception(f"Failed to save kym event results to {selected_path}: {exc}")
            ui.notify(f"Failed to save results: {exc}", type="negative")

    def _on_reset_event_params_click(self) -> None:
        """Reset event analysis parameter inputs to BaselineDropParams class defaults."""
        # Read defaults from class definition (no BaselineDropParams instance)
        defaults = {
            f.name: f.default
            for f in dataclasses.fields(BaselineDropParams)
            if f.default is not dataclasses.MISSING
        }
        if self._win_cmp_sec_input is not None and "win_cmp_sec" in defaults:
            self._win_cmp_sec_input.value = defaults["win_cmp_sec"]
        if self._smooth_sec_input is not None and "smooth_sec" in defaults:
            self._smooth_sec_input.value = defaults["smooth_sec"]
        if self._mad_k_input is not None and "mad_k" in defaults:
            self._mad_k_input.value = defaults["mad_k"]
        if self._abs_score_floor_input is not None and "abs_score_floor" in defaults:
            self._abs_score_floor_input.value = defaults["abs_score_floor"]

    def _collect_baseline_drop_params(self) -> BaselineDropParams:
        """Read baseline-drop parameters from the Event Analysis inputs."""
        default_params = BaselineDropParams()
        win_cmp_sec = default_params.win_cmp_sec
        smooth_sec = default_params.smooth_sec
        mad_k = default_params.mad_k
        abs_score_floor = default_params.abs_score_floor

        if self._win_cmp_sec_input is not None:
            try:
                win_cmp_sec = float(self._win_cmp_sec_input.value) if self._win_cmp_sec_input.value is not None else default_params.win_cmp_sec
            except (ValueError, TypeError):
                win_cmp_sec = default_params.win_cmp_sec

        if self._smooth_sec_input is not None:
            try:
                smooth_sec = float(self._smooth_sec_input.value) if self._smooth_sec_input.value is not None else default_params.smooth_sec
            except (ValueError, TypeError):
                smooth_sec = default_params.smooth_sec

        if self._mad_k_input is not None:
            try:
                mad_k = float(self._mad_k_input.value) if self._mad_k_input.value is not None else default_params.mad_k
            except (ValueError, TypeError):
                mad_k = default_params.mad_k

        if self._abs_score_floor_input is not None:
            try:
                abs_score_floor = float(self._abs_score_floor_input.value) if self._abs_score_floor_input.value is not None else default_params.abs_score_floor
            except (ValueError, TypeError):
                abs_score_floor = default_params.abs_score_floor

        return BaselineDropParams(
            win_cmp_sec=win_cmp_sec,
            smooth_sec=smooth_sec,
            mad_k=mad_k,
            abs_score_floor=abs_score_floor,
        )

    def get_baseline_params_for_batch(
        self,
    ) -> tuple[BaselineDropParams, NanGapParams | None, ZeroGapParams | None]:
        """Return baseline and gap params for batch analysis (matches single-file detect defaults).

        Returns:
            Tuple of ``(baseline_drop_params, nan_gap_params, zero_gap_params)``.
            Gap params are ``None`` to match :class:`DetectEvents` single-file emission.
        """
        return (self._collect_baseline_drop_params(), None, None)

    def _on_batch_kym_event_click(self) -> None:
        """Open batch kym-event dialog (callback provided by HomePage)."""
        if self._on_batch_kym_event is not None:
            self._on_batch_kym_event()

    def _on_detect_events_click(self) -> None:
        """Handle Detect Events button click."""
        # Verify file is still valid (safety check)
        if self._current_file is None:
            ui.notify("Select a file first", color="warning")
            return

        # Require ROI selection before starting detection
        if self._current_roi_id is None:
            ui.notify("Select an ROI first", color="warning")
            return

        baseline_drop_params = self._collect_baseline_drop_params()

        # Emit DetectEvents intent event
        path_str = str(self._current_file.path) if self._current_file.path else None
        self._on_detect_events(
            DetectEvents(
                roi_id=self._current_roi_id,
                channel=self._current_channel,
                path=path_str,
                baseline_drop_params=baseline_drop_params,
                phase="intent",
            )
        )

    def _on_batch_radon_click(self) -> None:
        """Open batch Radon analysis dialog."""
        if self._on_batch_radon is not None:
            self._on_batch_radon()

    # Commented out: Detect Events (all files) disabled
    # def _on_detect_all_events_click(self) -> None:
    #     """Handle Detect Events (all files) button click."""
    #     # Collect parameter values from inputs (same as single-file)
    #     default_params = BaselineDropParams()
    #     win_cmp_sec = default_params.win_cmp_sec
    #     smooth_sec = default_params.smooth_sec
    #     mad_k = default_params.mad_k
    #     abs_score_floor = default_params.abs_score_floor
    #     
    #     if self._win_cmp_sec_input is not None:
    #         try:
    #             win_cmp_sec = float(self._win_cmp_sec_input.value) if self._win_cmp_sec_input.value is not None else default_params.win_cmp_sec
    #         except (ValueError, TypeError):
    #             win_cmp_sec = default_params.win_cmp_sec
    #     
    #     if self._smooth_sec_input is not None:
    #         try:
    #             smooth_sec = float(self._smooth_sec_input.value) if self._smooth_sec_input.value is not None else default_params.smooth_sec
    #         except (ValueError, TypeError):
    #             smooth_sec = default_params.smooth_sec
    #     
    #     if self._mad_k_input is not None:
    #         try:
    #             mad_k = float(self._mad_k_input.value) if self._mad_k_input.value is not None else default_params.mad_k
    #         except (ValueError, TypeError):
    #             mad_k = default_params.mad_k
    #     
    #     if self._abs_score_floor_input is not None:
    #         try:
    #             abs_score_floor = float(self._abs_score_floor_input.value) if self._abs_score_floor_input.value is not None else default_params.abs_score_floor
    #         except (ValueError, TypeError):
    #             abs_score_floor = default_params.abs_score_floor
    #
    #     # Create BaselineDropParams with collected values (other params use defaults)
    #     baseline_drop_params = BaselineDropParams(
    #         win_cmp_sec=win_cmp_sec,
    #         smooth_sec=smooth_sec,
    #         mad_k=mad_k,
    #         abs_score_floor=abs_score_floor,
    #     )
    #
    #     # Emit DetectEvents intent event with all_files=True
    #     # Note: roi_id and path are None for all-files mode
    #     self._on_detect_events(
    #         DetectEvents(
    #             roi_id=None,
    #             path=None,
    #             all_files=True,
    #             baseline_drop_params=baseline_drop_params,
    #             phase="intent",
    #         )
    #     )
