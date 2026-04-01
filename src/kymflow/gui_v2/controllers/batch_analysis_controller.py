"""Controller for batch analysis flows (kym-event batch first)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Literal

from nicegui import ui

from kymflow.core.analysis.velocity_events.velocity_events import (
    BaselineDropParams,
    NanGapParams,
    ZeroGapParams,
)
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.app_context import AppContext
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import is_client_alive
from kymflow.core.kym_analysis_batch.types import BatchFileResult
from kymflow.gui_v2.events import DetectEvents, FileSelection, SelectionOrigin
from kymflow.gui_v2.events_state import RadonReportUpdated, VelocityEventDbUpdated
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.tasks import run_batch_kym_event_analysis, run_batch_radon_analysis

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class BatchAnalysisController:
    """Start batch kym-event analysis using AppContext batch task state.

    Attributes:
        _app_state: Application state (file list, selection).
        _bus: Event bus for UI refresh events.
        _context: Shared context (batch / batch_overall :class:`~kymflow.core.state.TaskState`).
    """

    def __init__(self, app_state: AppState, bus: EventBus, context: AppContext) -> None:
        """Initialize the batch analysis controller.

        Args:
            app_state: Application state.
            bus: Event bus.
            context: Application context (batch task states).
        """
        self._app_state: AppState = app_state
        self._bus: EventBus = bus
        self._context: AppContext = context

    def emit_current_file_selection_state(self) -> None:
        """Emit :class:`FileSelection` (phase ``state``) for the current selection without changing AppState.

        Used after batch kym-event analysis so line viewer and event table refresh once for the
        file that remains selected.

        Returns:
            None.
        """
        if not is_client_alive():
            return
        kf = self._app_state.selected_file
        if kf is None:
            return
        path = str(kf.path) if kf.path is not None else None
        self._bus.emit(
            FileSelection(
                path=path,
                file=kf,
                origin=SelectionOrigin.EXTERNAL,
                phase="state",
                roi_id=self._app_state.selected_roi_id,
                channel=self._app_state.selected_channel,
                kym_event_selection=None,
            )
        )

    def run_kym_event_batch(
        self,
        *,
        kym_files: list[KymImage],
        roi_mode: Literal["existing", "new_full_image"],
        roi_id: int | None,
        channel: int,
        baseline_drop_params: BaselineDropParams,
        nan_gap_params: NanGapParams | None,
        zero_gap_params: ZeroGapParams | None,
        max_parallel_files: int = 4,
        on_batch_finished: Callable[[bool, list[BatchFileResult]], None] | None = None,
        on_batch_file_result: Callable[[BatchFileResult], None] | None = None,
    ) -> None:
        """Run batch velocity-event detection on the given files.

        Uses :func:`~kymflow.gui_v2.tasks.run_batch_kym_event_analysis` (core
        :class:`~kymflow.core.kym_analysis_batch.kym_analysis_batch.KymAnalysisBatch`)
        with ``batch_task`` / ``batch_overall_task``. Emits :class:`DetectEvents`
        (state) with a concrete ``path`` after each successful file for file-table
        row refresh only; velocity-event DB cache and ``VelocityEventDbUpdated`` are
        batched at the end (in-memory only).

        Args:
            kym_files: Files corresponding to the current file-table subset.
            roi_mode: Analyze a shared ROI id or create a full-image ROI per file.
            roi_id: ROI id when ``roi_mode == \"existing\"``.
            channel: 1-based channel index.
            baseline_drop_params: Baseline-drop parameters.
            nan_gap_params: Optional NaN-gap parameters.
            zero_gap_params: Optional zero-gap parameters.
            max_parallel_files: Concurrent file workers for core batch runner.
            on_batch_finished: Optional callback after the batch task marks finished
                (success or cancel); receives ``True`` if the worker completed without cancel.
            on_batch_file_result: Optional per-file result on the UI thread (e.g. batch dialog).
        """
        files_list = self._app_state.files
        if files_list is None:
            ui.notify("No file list loaded", color="warning")
            return
        if not kym_files:
            ui.notify("No files to analyze", color="warning")
            return

        def on_file_complete(kf: KymImage) -> None:
            p = str(kf.path) if getattr(kf, "path", None) is not None else None
            self._bus.emit(
                DetectEvents(
                    roi_id=roi_id,
                    channel=channel,
                    path=p,
                    phase="state",
                )
            )

        def on_finalize_batch_velocity_cache(had_updates: bool) -> None:
            if had_updates:
                self._bus.emit(VelocityEventDbUpdated())

        def on_batch_complete(success: bool, results: list[BatchFileResult]) -> None:
            if success:
                ui.notify("Batch kym-event analysis finished", color="positive")
            else:
                ui.notify("Batch kym-event analysis stopped", color="warning")
            self.emit_current_file_selection_state()
            if on_batch_finished is not None:
                on_batch_finished(success, results)

        run_batch_kym_event_analysis(
            kym_files,
            files_list,
            self._context.batch_task,
            self._context.batch_overall_task,
            roi_mode=roi_mode,
            roi_id=roi_id,
            channel=channel,
            baseline_drop_params=baseline_drop_params,
            nan_gap_params=nan_gap_params,
            zero_gap_params=zero_gap_params,
            max_parallel_files=max_parallel_files,
            app_context=self._context,
            on_file_complete=on_file_complete,
            on_finalize_batch_velocity_cache=on_finalize_batch_velocity_cache,
            on_batch_complete=on_batch_complete,
            on_batch_file_result=on_batch_file_result,
        )

    def run_radon_batch(
        self,
        *,
        kym_files: list[KymImage],
        roi_mode: Literal["existing", "new_full_image"],
        roi_id: int | None,
        channel: int,
        window_size: int,
        max_parallel_files: int = 4,
        on_batch_finished: Callable[[bool, list[BatchFileResult]], None] | None = None,
        on_batch_file_result: Callable[[BatchFileResult], None] | None = None,
    ) -> None:
        """Run batch Radon analysis with deferred cache refresh and summary callback.

        Args:
            kym_files: Files to analyze.
            roi_mode: Existing shared ROI or new full-image ROI per file.
            roi_id: ROI id when ``roi_mode == \"existing\"``.
            channel: 1-based channel index.
            window_size: Radon window size.
            max_parallel_files: Concurrent file workers.
            on_batch_finished: Optional callback when the batch finishes.
            on_batch_file_result: Optional per-file result on the UI thread (e.g. batch dialog).
        """
        files_list = self._app_state.files
        if files_list is None:
            ui.notify("No file list loaded", color="warning")
            return
        if not kym_files:
            ui.notify("No files to analyze", color="warning")
            return

        def on_finalize_batch_radon_cache(had_updates: bool) -> None:
            if had_updates:
                self._bus.emit(RadonReportUpdated())

        def on_batch_complete(success: bool, results: list[BatchFileResult]) -> None:
            if success:
                ui.notify("Batch flow analysis finished", color="positive")
            else:
                ui.notify("Batch flow analysis stopped", color="warning")
            self.emit_current_file_selection_state()
            if on_batch_finished is not None:
                on_batch_finished(success, results)

        run_batch_radon_analysis(
            kym_files,
            files_list,
            self._context.batch_task,
            self._context.batch_overall_task,
            roi_mode=roi_mode,
            roi_id=roi_id,
            channel=channel,
            window_size=window_size,
            max_parallel_files=max_parallel_files,
            on_finalize_batch_radon_cache=on_finalize_batch_radon_cache,
            on_batch_complete=on_batch_complete,
            on_batch_file_result=on_batch_file_result,
        )
