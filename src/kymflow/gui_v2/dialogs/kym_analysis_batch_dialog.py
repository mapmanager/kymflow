"""Modal dialog for batch kym-analysis across filtered files."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable, Literal

from nicegui import ui
from nicegui.client import Client

from kymflow.core.analysis.velocity_events.velocity_events import (
    BaselineDropParams,
    NanGapParams,
    ZeroGapParams,
)
from kymflow.core.kym_analysis_batch import batch_file_result_to_table_row, preview_batch_table_rows
from kymflow.core.kym_analysis_batch.kym_event_batch import roi_intersection_across_files
from kymflow.core.kym_analysis_batch.types import AnalysisBatchKind, BatchFileResult
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage
    from kymflow.gui_v2.app_context import AppContext
    from kymflow.gui_v2.controllers.batch_analysis_controller import BatchAnalysisController
    from kymflow.gui_v2.state import AppState
    from kymflow.gui_v2.views.file_table_view import FileTableView

logger = get_logger(__name__)


class KymAnalysisBatchDialog:
    """Modal for batch analysis over the filtered file table.

    Create a **new** instance per open (e.g. from a toolbar handler). Call
    :meth:`schedule_open` once; after the user closes the dialog, :meth:`dispose`
    removes the UI tree and cancels the poll timer. Do not touch widgets after
    ``dispose``.

    Stays open during the batch with overall file progress. Quasar ``persistent``
    reduces accidental backdrop dismiss; **Close** is disabled while the batch runs;
    **Cancel** requests task cancellation. After completion, **Done** and **Close**
    call :meth:`dispose`.

    Attributes:
        _app_state: Application state (channel selection).
        _file_table_view: File table used to obtain filtered rows.
        _batch_controller: Starts core-backed batch via :class:`BatchAnalysisController`.
        _context: Application context (batch :class:`~kymflow.core.state.TaskState` for progress).
        _get_baseline_params: Returns baseline (and optional gap) params from toolbar inputs.
    """

    def __init__(
        self,
        app_state: "AppState",
        file_table_view: "FileTableView",
        batch_controller: "BatchAnalysisController",
        context: "AppContext",
        *,
        get_baseline_params: Callable[
            [],
            tuple[BaselineDropParams, NanGapParams | None, ZeroGapParams | None],
        ],
        on_disposed: Callable[[], None] | None = None,
    ) -> None:
        """Store dependencies; UI is built in :meth:`schedule_open` (sync client context).

        Args:
            app_state: Application state.
            file_table_view: File table view.
            batch_controller: Batch analysis controller.
            context: Application context (batch task states, suppression flag).
            get_baseline_params: Callable returning ``(baseline, nan_gap, zero_gap)``.
            on_disposed: Optional callback after timer cancel and dialog ``delete()`` (e.g. re-entrancy guard).
        """
        self._app_state = app_state
        self._file_table_view = file_table_view
        self._batch_controller = batch_controller
        self._context = context
        self._get_baseline_params = get_baseline_params
        self._on_disposed = on_disposed

        self._is_active: bool = False
        self._dialog: ui.dialog | None = None
        self._kind: AnalysisBatchKind = AnalysisBatchKind.KYM_EVENT
        self._channel_label: ui.label | None = None
        self._kind_label: ui.label | None = None
        self._roi_mode_radio_wrap: ui.column | None = None
        self._roi_mode_radio: ui.radio | None = None
        self._roi_select: ui.select | None = None
        self._window_size_select: ui.select | None = None
        self._radon_options_column: ui.column | None = None
        self._analyze_button: ui.button | None = None
        self._close_button: ui.button | None = None
        self._cancel_run_button: ui.button | None = None
        self._progress_bar: ui.linear_progress | None = None
        self._progress_caption: ui.label | None = None
        self._done_label: ui.label | None = None
        self._progress_column: ui.column | None = None
        self._report_scroll: ui.scroll_area | None = None
        self._report_table: ui.table | None = None
        self._poll_timer: ui.timer | None = None
        self._batch_ui_running: bool = False
        self._snapshot_kym_files: list[KymImage] | None = None

    def _build_ui(self) -> None:
        """Create dialog subtree and poll timer (must run under NiceGUI client context)."""
        if self._dialog is not None:
            return
        with ui.dialog() as self._dialog, ui.card().classes("w-full max-w-lg"):
            self._dialog.props("persistent")
            ui.label("Batch analysis").classes("text-lg font-semibold")
            self._kind_label = ui.label("").classes("text-sm text-gray-600")
            self._channel_label = ui.label("").classes("text-sm")
            with ui.column().classes("w-full gap-1") as self._roi_mode_radio_wrap:
                self._roi_mode_radio = ui.radio(
                    {
                        "existing": "Analyze existing ROI (shared across files)",
                        "new_full_image": "Analyze new ROI (full image, per file)",
                    },
                    value="existing",
                    on_change=lambda _: self._on_roi_mode_changed(),
                ).props("dense")
            self._roi_select = ui.select(
                options={},
                label="ROI (intersection of filtered rows)",
                value=None,
            ).classes("w-full")
            with ui.column().classes("w-full gap-1") as self._radon_options_column:
                self._window_size_select = ui.select(
                    options=[16, 32, 64, 128, 256],
                    value=16,
                    label="Radon window size",
                ).classes("w-36")
                self._radon_options_column.visible = False
            with ui.column().classes("w-full gap-1") as self._progress_column:
                self._progress_column.visible = False
                self._progress_bar = ui.linear_progress(
                    value=0.0,
                    show_value=False,
                ).props("instant-feedback")
                self._progress_caption = ui.label("").classes("text-xs text-gray-600")
            with (
                ui.scroll_area()
                .classes("w-full")
                .style("max-height: 14rem; max-width: 100%")
                .props("horizontal")
                as self._report_scroll
            ):
                self._report_table = ui.table(
                    columns=[
                        {"name": "file", "label": "File", "field": "file"},
                        {"name": "kind", "label": "Analysis", "field": "kind"},
                        {"name": "outcome", "label": "Outcome", "field": "outcome"},
                        {"name": "message", "label": "Message", "field": "message"},
                    ],
                    rows=[],
                    row_key="file",
                ).classes("w-full text-xs")
            self._set_report_table_visible(False)
            self._done_label = ui.label("").classes("text-sm font-medium")
            self._done_label.visible = False
            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                self._close_button = ui.button("Close", on_click=self._on_close_click).props("outline")
                self._cancel_run_button = ui.button("Cancel", on_click=self._on_cancel_run_click)
                self._cancel_run_button.visible = False
                self._analyze_button = ui.button("Analyze", on_click=self._on_analyze_click)
        self._poll_timer = ui.timer(0.15, self._poll_batch_progress)
        self._configure_roi_mode_radio_for_kind()
        self._sync_roi_controls()
        self._reset_idle_chrome()

    def dispose(self) -> None:
        """Stop timer, close and delete dialog DOM, clear active flag, run ``on_disposed``.

        Safe to call more than once. Order: ``_is_active = False`` first so timer/callbacks
        no-op; then cancel timer; then ``close()`` and ``delete()`` on the dialog element.
        """
        self._is_active = False
        if self._poll_timer is not None:
            try:
                self._poll_timer.cancel()
            except Exception:
                logger.exception("batch dialog timer cancel failed")
            self._poll_timer = None
        dlg = self._dialog
        self._dialog = None
        if dlg is not None:
            try:
                dlg.close()
            except Exception:
                logger.exception("batch dialog close failed")
            try:
                dlg.delete()
            except Exception:
                logger.exception("batch dialog delete failed")
        cb = self._on_disposed
        self._on_disposed = None
        if cb is not None:
            try:
                cb()
            except Exception:
                logger.exception("batch dialog on_disposed failed")

    def _set_report_table_visible(self, visible: bool) -> None:
        """Show or hide the report table and its scroll container together."""
        if not self._is_active:
            return
        if self._report_scroll is not None:
            self._report_scroll.visible = visible
        if self._report_table is not None:
            self._report_table.visible = visible

    def _configure_roi_mode_radio_for_kind(self) -> None:
        """Kym-event: only existing ROI; hide ROI mode radio. Radon: show radio with both modes."""
        if not self._is_active or self._roi_mode_radio is None:
            return
        existing_label = "Analyze existing ROI (shared across files)"
        new_label = "Analyze new ROI (full image, per file)"
        if self._kind == AnalysisBatchKind.KYM_EVENT:
            self._roi_mode_radio.options = {"existing": existing_label}
            self._roi_mode_radio.value = "existing"
            if self._roi_mode_radio_wrap is not None:
                self._roi_mode_radio_wrap.visible = False
        else:
            self._roi_mode_radio.options = {
                "existing": existing_label,
                "new_full_image": new_label,
            }
            self._roi_mode_radio.value = "existing"
            if self._roi_mode_radio_wrap is not None:
                self._roi_mode_radio_wrap.visible = True

    def _row_dict_from_result(self, r: BatchFileResult) -> dict[str, str]:
        """Map a batch result to a table row dict (core formatting, emoji outcomes)."""
        return batch_file_result_to_table_row(r)

    def _apply_file_result_row(self, r: BatchFileResult) -> None:
        """Replace one table row when a file finishes (running batch only)."""
        if not self._is_active:
            return
        if self._report_table is None or not self._batch_ui_running:
            return
        new_row = self._row_dict_from_result(r)
        rows = list(self._report_table.rows)
        key = new_row["file"]
        for i, row in enumerate(rows):
            if row["file"] == key:
                rows[i] = new_row
                break
        else:
            rows.append(new_row)
        self._report_table.rows = rows

    def _apply_preview_table(self) -> None:
        """Fill the report table from core preview (idle, dialog open)."""
        if not self._is_active:
            return
        if self._report_table is None or self._batch_ui_running:
            return
        files = self._snapshot_kym_files
        if not files:
            self._report_table.rows = []
            self._set_report_table_visible(False)
            return
        ch = self._app_state.selected_channel
        if ch is None:
            self._report_table.rows = []
            self._set_report_table_visible(False)
            return
        mode: Literal["existing", "new_full_image"] = self._roi_mode_radio.value  # type: ignore[assignment]
        roi_id: int | None
        if mode == "existing":
            if self._roi_select is None or self._roi_select.value is None:
                roi_id = None
            else:
                roi_id = int(self._roi_select.value)
        else:
            roi_id = None
        self._report_table.rows = preview_batch_table_rows(
            kind=self._kind,
            files=files,
            roi_mode=mode,
            roi_id=roi_id,
            channel=ch,
        )
        self._set_report_table_visible(True)

    def _on_roi_mode_changed(self) -> None:
        """ROI mode radio changed: refresh ROI select enable state and preview table."""
        self._sync_roi_controls()
        self._apply_preview_table()

    def _reset_idle_chrome(self) -> None:
        """Show controls for configuring a new batch (not running)."""
        if not self._is_active:
            return
        self._batch_ui_running = False
        if self._progress_column is not None:
            self._progress_column.visible = False
        if self._report_table is not None:
            self._report_table.rows = []
        self._set_report_table_visible(False)
        if self._done_label is not None:
            self._done_label.visible = False
            self._done_label.text = ""
        if self._progress_bar is not None:
            self._progress_bar.value = 0.0
        if self._progress_caption is not None:
            self._progress_caption.text = ""
        if self._close_button is not None:
            self._close_button.enable()
        if self._cancel_run_button is not None:
            self._cancel_run_button.visible = False
        if self._analyze_button is not None:
            self._analyze_button.enable()
        if self._roi_mode_radio is not None:
            self._roi_mode_radio.enable()
        if self._window_size_select is not None:
            self._window_size_select.enable()
        self._sync_roi_controls()

    def _set_running_chrome(self) -> None:
        """Disable form actions; show progress; **Close** off, **Cancel** on."""
        if not self._is_active:
            return
        self._batch_ui_running = True
        if self._progress_column is not None:
            self._progress_column.visible = True
        if self._done_label is not None:
            self._done_label.visible = False
        if self._close_button is not None:
            self._close_button.disable()
        if self._cancel_run_button is not None:
            self._cancel_run_button.visible = True
        if self._analyze_button is not None:
            self._analyze_button.disable()
        if self._roi_mode_radio is not None:
            self._roi_mode_radio.disable()
        if self._roi_select is not None:
            self._roi_select.disable()
        if self._window_size_select is not None:
            self._window_size_select.disable()

    def _set_done_chrome(self, success: bool, results: list[BatchFileResult]) -> None:
        """Batch finished: hide cancel, enable close, show summary."""
        if not self._is_active:
            return
        self._batch_ui_running = False
        if self._progress_column is not None:
            self._progress_column.visible = True
        if self._done_label is not None:
            self._done_label.visible = True
            self._done_label.text = "Done." if success else "Stopped."
        if self._report_table is not None:
            self._report_table.rows = [self._row_dict_from_result(r) for r in results]
        self._set_report_table_visible(True)
        if self._close_button is not None:
            self._close_button.enable()
        if self._cancel_run_button is not None:
            self._cancel_run_button.visible = False
        if self._analyze_button is not None:
            self._analyze_button.disable()
        if self._roi_mode_radio is not None:
            self._roi_mode_radio.disable()
        if self._roi_select is not None:
            self._roi_select.disable()
        if self._window_size_select is not None:
            self._window_size_select.disable()

    def _poll_batch_progress(self) -> None:
        """Mirror overall and per-file task state into dialog widgets."""
        if not self._is_active:
            return
        if not self._batch_ui_running:
            return
        ot = self._context.batch_overall_task
        bt = self._context.batch_task
        if self._progress_bar is not None:
            self._progress_bar.value = float(ot.progress)
        if self._progress_caption is not None:
            self._progress_caption.text = f"{ot.message} — {bt.message}"

    def _on_close_click(self) -> None:
        """Dispose dialog when idle or after batch completed."""
        if self._batch_ui_running:
            return
        self.dispose()

    def _on_cancel_run_click(self) -> None:
        """Request cancellation of the running batch (toolbar task state)."""
        if self._context.batch_overall_task is not None:
            self._context.batch_overall_task.request_cancel()
        if self._context.batch_task is not None:
            self._context.batch_task.request_cancel()

    def schedule_open(self, kind: AnalysisBatchKind) -> None:
        """Build UI, then load table snapshot and open (call from sync UI handler only)."""
        self._kind = kind
        try:
            client = ui.context.client
        except RuntimeError:
            logger.exception("Batch dialog open: no NiceGUI client in click handler")
            return
        self._is_active = True
        self._build_ui()
        asyncio.create_task(self._open_async(client))

    async def _open_async(self, client: Client) -> None:
        """Load filtered rows into controls, then open the dialog under ``client`` context."""
        await self._refresh_from_table()

        def _open_dialog() -> None:
            if not self._is_active:
                return
            self._reset_idle_chrome()
            if self._kind_label is not None:
                if self._kind == AnalysisBatchKind.RADON:
                    self._kind_label.text = "Flow analysis (Radon)"
                else:
                    self._kind_label.text = "Kym event detection"
            if self._radon_options_column is not None:
                self._radon_options_column.visible = self._kind == AnalysisBatchKind.RADON
            self._configure_roi_mode_radio_for_kind()
            self._apply_preview_table()
            if self._dialog is not None:
                self._dialog.open()

        client.safe_invoke(_open_dialog)

    async def _refresh_from_table(self) -> None:
        """Update channel label and ROI options from the current file table."""
        files = await self._file_table_view.get_displayed_kym_images_async()
        self._snapshot_kym_files = list(files)
        ch = self._app_state.selected_channel
        if self._channel_label is not None:
            self._channel_label.text = (
                f"Channel: {ch}" if ch is not None else "Channel: (select a channel in the viewer)"
            )
        inter = roi_intersection_across_files(files)
        if self._roi_select is not None:
            opts = {rid: f"ROI {rid}" for rid in inter}
            self._roi_select.options = opts
            self._roi_select.value = inter[0] if inter else None
        self._sync_roi_controls()

    def _sync_roi_controls(self) -> None:
        """Enable/disable ROI select from mode."""
        if not self._is_active:
            return
        if self._roi_select is None or self._roi_mode_radio is None:
            return
        if self._batch_ui_running:
            return
        mode = self._roi_mode_radio.value
        if mode == "existing":
            self._roi_select.enable()
        else:
            self._roi_select.disable()

    def _on_analyze_click(self) -> None:
        """Sync handler: only here is ``ui.context.client`` guaranteed (slot stack set)."""
        try:
            client = ui.context.client
        except RuntimeError:
            logger.exception("Batch analyze: no NiceGUI client in Analyze click handler")
            return
        asyncio.create_task(self._run_analyze_async(client))

    def _notify_client(self, client: Client, message: str, *, type_: str) -> None:
        """Show notification inside the given client's UI context."""

        def _show() -> None:
            ui.notify(message, type=type_)

        client.safe_invoke(_show)

    async def _run_analyze_async(self, client: Client) -> None:
        """Validate using async grid read; all UI side effects go through ``client.safe_invoke``.

        The asyncio task created by ``create_task`` has an empty NiceGUI slot stack, so
        this coroutine must not call ``ui.context.client``, ``ui.notify``, ``ui.timer``,
        or ``dialog.close`` directly—only :meth:`~nicegui.client.Client.safe_invoke`.
        """
        files = self._snapshot_kym_files
        if not files:
            files = await self._file_table_view.get_displayed_kym_images_async()
        if not files:
            self._notify_client(client, "No files in the current table view", type_="warning")
            return
        channel = self._app_state.selected_channel
        if channel is None:
            self._notify_client(client, "Select a channel first", type_="warning")
            return

        baseline_drop_params, nan_gap_params, zero_gap_params = self._get_baseline_params()
        mode: Literal["existing", "new_full_image"] = self._roi_mode_radio.value  # type: ignore[assignment]
        roi_id: int | None
        if mode == "existing":
            if self._roi_select is None or self._roi_select.value is None:
                self._notify_client(
                    client,
                    "No common ROI across filtered files — adjust the filter so files share an ROI",
                    type_="warning",
                )
                return
            roi_id = int(self._roi_select.value)
        else:
            roi_id = None

        def _start_batch() -> None:
            if not self._is_active:
                return
            self._set_running_chrome()

            def _on_batch_finished(success: bool, results: list[BatchFileResult]) -> None:
                self._set_done_chrome(success, results)

            def _on_batch_file_result(r: BatchFileResult) -> None:
                def _apply_row() -> None:
                    self._apply_file_result_row(r)

                client.safe_invoke(_apply_row)

            if self._kind == AnalysisBatchKind.RADON:
                window_size = 16
                if self._window_size_select is not None and self._window_size_select.value is not None:
                    window_size = int(self._window_size_select.value)
                self._batch_controller.run_radon_batch(
                    kym_files=files,
                    roi_mode=mode,
                    roi_id=roi_id,
                    channel=channel,
                    window_size=window_size,
                    on_batch_finished=_on_batch_finished,
                    on_batch_file_result=_on_batch_file_result,
                )
            else:
                self._batch_controller.run_kym_event_batch(
                    kym_files=files,
                    roi_mode=mode,
                    roi_id=roi_id,
                    channel=channel,
                    baseline_drop_params=baseline_drop_params,
                    nan_gap_params=nan_gap_params,
                    zero_gap_params=zero_gap_params,
                    on_batch_finished=_on_batch_finished,
                    on_batch_file_result=_on_batch_file_result,
                )

        client.safe_invoke(_start_batch)
