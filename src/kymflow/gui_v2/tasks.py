"""Thread/process-safe helpers for running analysis routines without blocking NiceGUI.

Key rule: **only the NiceGUI main event loop updates UI-bound state**.

We run CPU-heavy analysis in a background thread (non-daemon). Any progress,
errors, cancellation, and completion are communicated back to the NiceGUI
thread via a `queue.Queue`, and applied using a `ui.timer(...)` poller.

This pattern keeps multiprocessing (in core) compatible with NiceGUI.
"""

from __future__ import annotations

import queue
import threading
from typing import TYPE_CHECKING, Callable, Literal, Optional, Sequence, Tuple, Any, Union

from nicegui import ui

from kymflow.core.analysis.velocity_events.velocity_events import (
    BaselineDropParams,
    NanGapParams,
    ZeroGapParams,
)
from kymflow.core.batch_analysis.kym_analysis_batch import KymAnalysisBatch
from kymflow.core.batch_analysis.kym_event_batch_strategy import KymEventBatchStrategy
from kymflow.core.batch_analysis.radon_batch_strategy import RadonBatchStrategy
from kymflow.core.batch_analysis.types import BatchFileOutcome, BatchFileResult
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.analysis.kym_flow_radon import FlowCancelled
from kymflow.core.state import TaskState
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    from kymflow.gui_v2.app_context import AppContext

logger = get_logger(__name__)

# Message protocol sent from worker thread -> NiceGUI main loop
# - ('progress', completed:int, total:int)
# - ('done', True)
# - ('cancelled', None)
# - ('error', 'message')
Msg = Union[
    Tuple[str, int, int],
    Tuple[str, Any],
]


def run_flow_analysis(
    kym_file: KymImage,
    task_state: TaskState,
    *,
    window_size: int = 16,
    roi_id: int,
    channel: int,
    on_result: Optional[Callable[[bool], None]] = None,
) -> None:
    """Run Radon flow analysis on a single ROI without blocking NiceGUI.

    Notes:
    - Multiprocessing lives in core (`mp_analyze_flow`).
    - This function never updates UI-bound state from background threads.
    - Cancellation is *brutal*: we terminate the multiprocessing pool and
      discard results (per your spec).

    Args:
        kym_file: KymImage instance to analyze.
        task_state: TaskState object for progress tracking and cancellation.
        window_size: Number of time lines per analysis window.
        roi_id: Identifier of the ROI to analyze. Must exist.
        channel: 1-based channel index to analyze. Must be provided by caller.
        on_result: Optional callback invoked on successful completion.
            Runs on the NiceGUI main loop.
    """

    # Validate roi_id early, while we still have UI context.
    if roi_id is None:
        task_state.set_running(True)
        task_state.message = "Error: ROI ID is required"
        task_state.mark_finished()
        return

    roi = kym_file.rois.get(roi_id)
    if roi is None:
        task_state.set_running(True)
        task_state.message = f"Error: ROI {roi_id} not found"
        task_state.mark_finished()
        return

    # check if we have v0 analysis and do not run new analysis
    # never allow new analysis on old v0 velocity
    # in gui, we should never get here, button 'analyze flow' has guard
    ka = kym_file.get_kym_analysis()
    radon = ka.get_analysis_object("RadonAnalysis")
    if radon is not None and radon.has_v0_flow_analysis(roi_id, channel):
        logger.warning(f"ROI {roi_id} already has v0 analysis (channel={channel}), cannot run new analysis")
        return

    progress_q: queue.Queue[Msg] = queue.Queue()
    cancel_event = threading.Event()

    # --- UI/main-loop poller (safe place to touch task_state and UI) ---
    timer = None  # assigned below

    def _drain_queue() -> None:
        nonlocal timer
        drained_any = False

        while True:
            try:
                msg = progress_q.get_nowait()
            except queue.Empty:
                break

            drained_any = True
            tag = msg[0]

            if tag == "progress":
                # ('progress', completed, total)
                _, completed, total = msg  # type: ignore[misc]
                pct = (completed / total) if total else 0.0
                pct = max(0.0, min(1.0, float(pct)))
                task_state.set_progress(pct, f"{completed}/{total} windows")
            elif tag == "done":
                task_state.message = "Flow analysis complete"
                task_state.mark_finished()
                
                # Log success with details
                logger.info("\n" + "=" * 80)
                logger.info("SUCCESS: Multiprocessing Radon flow analysis completed")
                logger.info(f"  File: {kym_file.path if hasattr(kym_file, 'path') else 'N/A'}")
                logger.info(f"  ROI ID: {roi_id}")
                logger.info(f"  Window size: {window_size}")
                logger.info(f"  Final progress: {task_state.progress:.1%}")
                logger.info("=" * 80 + "\n")
                
                if on_result:
                    try:
                        on_result(True)
                    except Exception:
                        logger.exception("on_result callback failed")
                if timer is not None:
                    timer.cancel()
            elif tag == "cancelled":
                task_state.message = "Flow analysis cancelled"
                task_state.mark_finished()
                if timer is not None:
                    timer.cancel()
            elif tag == "error":
                # ('error', 'message')
                task_state.message = f"Flow analysis error: {msg[1]}"
                task_state.mark_finished()
                if timer is not None:
                    timer.cancel()
            else:
                logger.warning("Unknown worker message: %r", msg)

        # If nothing to drain, no-op. (Timer keeps running.)
        _ = drained_any

    # Create the poller timer *in the current NiceGUI client context*.
    timer = ui.timer(0.1, _drain_queue)

    # --- Worker thread (never touches UI directly) ---
    def _worker() -> None:
        try:
            # Show initial state quickly (but via queue to keep one pathway)
            progress_q.put(("progress", 0, 1))

            radon = kym_file.get_kym_analysis().get_analysis_object("RadonAnalysis")
            if radon is not None:
                radon.analyze_roi(
                    roi_id,
                    channel,
                    window_size,
                    progress_queue=progress_q,
                    is_cancelled=cancel_event.is_set,
                    use_multiprocessing=True,
                )
        except FlowCancelled:
            progress_q.put(("cancelled", None))
        except Exception as exc:  # surfaced to UI
            logger.exception("Flow analysis failed")
            progress_q.put(("error", repr(exc)))
        else:
            progress_q.put(("done", True))

    # --- Cancel handler (called from UI) ---
    def _handle_cancel() -> None:
        cancel_event.set()

    task_state.on_cancelled(_handle_cancel)

    # Mark running immediately so UI can react before heavy work begins
    # Set cancellable BEFORE set_running so the bridge emits the correct state
    # IMPORTANT: set_running triggers the bridge to emit, so cancellable must be set first
    task_state.cancellable = True
    # logger.debug(f"Set cancellable=True, running={task_state.running}")
    task_state.set_running(True)
    # logger.debug(f"After set_running(True), cancellable={task_state.cancellable}, running={task_state.running}")
    task_state.set_progress(0.0, "Starting analysis")
    # logger.debug(f"After set_progress, cancellable={task_state.cancellable}, running={task_state.running}")

    # IMPORTANT: non-daemon. We want deterministic cleanup of pools.
    threading.Thread(target=_worker, daemon=False).start()


def run_batch_flow_analysis(
    kym_files: Sequence[KymImage],
    per_file_task: TaskState,
    overall_task: TaskState,
    *,
    window_size: int = 16,
    channel: int,
    on_file_complete: Optional[Callable[[KymImage], None]] = None,
    on_batch_complete: Optional[Callable[[bool], None]] = None,
) -> None:
    """Run flow analysis for multiple files sequentially without blocking NiceGUI.

    Design choices:
    - Files are processed sequentially in one background thread. (You already
      have multiprocessing inside each ROI analysis; adding more parallelism at
      the batch level can oversubscribe CPU and hurt UX.)
    - Cancellation is brutal: terminate pool and discard results.
    - Progress is communicated via queue and applied on NiceGUI loop.

    Files without ROIs are skipped.

    Args:
        kym_files: KymImage objects to analyze.
        per_file_task: TaskState for current file progress.
        overall_task: TaskState for overall batch progress.
            window_size: Radon window size.
            channel: 1-based channel index to analyze for all ROIs in all files.
        on_file_complete: Callback after each file completes (NiceGUI thread).
        on_batch_complete: Callback after batch completes (NiceGUI thread).
    """
    progress_q: queue.Queue[Tuple[str, Any]] = queue.Queue()
    cancel_event = threading.Event()
    files = list(kym_files)
    total_files = len(files)
    if total_files == 0:
        return

    timer = None  # assigned below

    def _drain_queue() -> None:
        nonlocal timer
        while True:
            try:
                tag, payload = progress_q.get_nowait()
            except queue.Empty:
                break

            if tag == "overall":
                completed, total = payload
                pct = (completed / total) if total else 0.0
                overall_task.set_progress(float(pct), f"{completed}/{total} files")
            elif tag == "per_file":
                completed, total, name = payload
                pct = (completed / total) if total else 0.0
                per_file_task.set_progress(float(pct), f"{name}: {completed}/{total} windows")
            elif tag == "file_done":
                kym_file = payload
                if on_file_complete:
                    try:
                        on_file_complete(kym_file)
                    except Exception:
                        logger.exception("on_file_complete failed")
            elif tag == "done":
                overall_task.message = "Done"
                per_file_task.message = "Done"
                overall_task.mark_finished()
                per_file_task.mark_finished()
                if on_batch_complete:
                    try:
                        on_batch_complete(True)
                    except Exception:
                        logger.exception("on_batch_complete failed")
                if timer is not None:
                    timer.cancel()
            elif tag == "cancelled":
                overall_task.message = "Cancelled"
                per_file_task.message = "Cancelled"
                overall_task.mark_finished()
                per_file_task.mark_finished()
                if on_batch_complete:
                    try:
                        on_batch_complete(False)
                    except Exception:
                        logger.exception("on_batch_complete failed")
                if timer is not None:
                    timer.cancel()
            elif tag == "error":
                overall_task.message = f"Error: {payload}"
                per_file_task.message = f"Error: {payload}"
                overall_task.mark_finished()
                per_file_task.mark_finished()
                if on_batch_complete:
                    try:
                        on_batch_complete(False)
                    except Exception:
                        logger.exception("on_batch_complete failed")
                if timer is not None:
                    timer.cancel()
            else:
                logger.warning("Unknown batch worker message: %r", (tag, payload))

    timer = ui.timer(0.1, _drain_queue)

    def _worker() -> None:
        try:
            total_files = len(files)
            overall_done = 0
            progress_q.put(("overall", (overall_done, total_files)))

            for kym_file in files:
                if cancel_event.is_set():
                    raise FlowCancelled("Batch cancelled")

                # Skip files without ROIs
                if not getattr(kym_file, "rois", None):
                    overall_done += 1
                    progress_q.put(("overall", (overall_done, total_files)))
                    continue

                # Choose ROI: if multiple, analyze each? Current behavior: analyze all ROIs sequentially.
                roi_ids = kym_file.rois.get_roi_ids()
                
                # Skip files with no ROIs
                if not roi_ids:
                    overall_done += 1
                    progress_q.put(("overall", (overall_done, total_files)))
                    continue

                for roi_id in roi_ids:
                    if cancel_event.is_set():
                        raise FlowCancelled("Batch cancelled")

                    # Create per-ROI queue to forward progress to batch queue
                    roi_progress_q: queue.Queue[Msg] = queue.Queue()
                    file_name = str(kym_file.path.name)

                    # Start a thread to forward ROI progress to batch queue
                    def _forward_roi_progress() -> None:
                        """Forward ROI progress messages to batch queue."""
                        while True:
                            try:
                                msg = roi_progress_q.get(timeout=0.1)
                            except queue.Empty:
                                continue

                            if msg[0] == "progress":
                                # Forward as per_file message with file name
                                _, completed, total = msg  # type: ignore[misc]
                                progress_q.put(("per_file", (int(completed), int(total), file_name)))
                            elif msg[0] == "done":
                                break

                    forward_thread = threading.Thread(target=_forward_roi_progress, daemon=True)
                    forward_thread.start()

                    radon = kym_file.get_kym_analysis().get_analysis_object("RadonAnalysis")
                    if radon is not None:
                        radon.analyze_roi(
                            roi_id,
                            channel,
                            window_size,
                            progress_queue=roi_progress_q,
                            is_cancelled=cancel_event.is_set,
                            use_multiprocessing=True,
                        )
                    
                    # Signal done to forward thread
                    roi_progress_q.put(("done", None))
                    forward_thread.join(timeout=1.0)

                overall_done += 1
                progress_q.put(("overall", (overall_done, total_files)))
                progress_q.put(("file_done", kym_file))

            progress_q.put(("done", None))
        except FlowCancelled:
            progress_q.put(("cancelled", None))
        except Exception as exc:
            logger.exception("Batch flow analysis failed")
            progress_q.put(("error", repr(exc)))

    def _handle_cancel() -> None:
        cancel_event.set()

    overall_task.on_cancelled(_handle_cancel)
    per_file_task.on_cancelled(_handle_cancel)

    overall_task.set_running(True)
    overall_task.cancellable = True
    overall_task.set_progress(0.0, "Starting batch")

    per_file_task.set_running(True)
    per_file_task.cancellable = True
    per_file_task.set_progress(0.0, "Waiting")

    threading.Thread(target=_worker, daemon=False).start()


def run_batch_kym_event_analysis(
    kym_files: Sequence[KymImage],
    image_list: KymImageList,
    per_file_task: TaskState,
    overall_task: TaskState,
    *,
    roi_mode: Literal["existing", "new_full_image"],
    roi_id: int | None,
    channel: int,
    baseline_drop_params: BaselineDropParams,
    nan_gap_params: NanGapParams | None = None,
    zero_gap_params: ZeroGapParams | None = None,
    max_parallel_files: int = 4,
    app_context: Optional["AppContext"] = None,
    on_file_complete: Optional[Callable[[KymImage], None]] = None,
    on_finalize_batch_velocity_cache: Optional[Callable[[bool], None]] = None,
    on_batch_complete: Optional[Callable[[bool, list[BatchFileResult]], None]] = None,
    on_batch_file_result: Optional[Callable[[BatchFileResult], None]] = None,
) -> None:
    """Run velocity event detection on multiple files without blocking NiceGUI.

    Work runs in a background thread; progress is applied on the NiceGUI loop via
    a timer queue. Per-file :meth:`KymImageList.update_velocity_event_cache_only`
    is deferred until a single ``finalize_cache`` step on the main loop after the
    worker finishes (in-memory only; CSV is not written here).

    When ``app_context`` is provided, ``suppress_velocity_event_cache_sync_on_detect_events``
    is set for the duration of the run so :class:`DetectEvents` (state) from the
    batch does not update the velocity-event DB per file via
    :class:`~kymflow.gui_v2.controllers.kym_event_cache_sync_controller.KymEventCacheSyncController`.

    Files without Radon ``velocity`` / ``time`` for the effective ROI/channel are
    skipped with a per-file status message. For ``roi_mode == \"new_full_image\"``,
    a full-image ROI is created per file via :meth:`~kymflow.core.image_loaders.roi.RoiSet.create_roi`
    with no arguments before checking Radon prerequisites.

    Args:
        kym_files: Files to analyze (e.g. filtered file-table rows).
        image_list: ``AcqImageList`` / ``KymImageList`` used to refresh the velocity-event cache.
        per_file_task: Task state for current-file status text.
        overall_task: Task state for overall batch progress.
        roi_mode: Use a shared existing ROI id or create a new full-image ROI per file.
        roi_id: ROI id when ``roi_mode == \"existing\"``; ignored for ``new_full_image``.
        channel: 1-based channel index for all files.
        baseline_drop_params: Baseline-drop detection parameters.
        nan_gap_params: Optional NaN-gap parameters (defaults inside analysis if None).
        zero_gap_params: Optional zero-gap parameters (defaults inside analysis if None).
        max_parallel_files: Concurrent file workers for :class:`~kymflow.core.batch_analysis.kym_analysis_batch.KymAnalysisBatch`.
        app_context: Optional application context used to suppress per-file cache sync on ``DetectEvents``.
        on_file_complete: Optional callback after each successful detection (main loop); e.g. row refresh.
        on_finalize_batch_velocity_cache: Optional callback after in-memory cache rebuild; argument is
            True if at least one file succeeded so the caller may emit ``VelocityEventDbUpdated``.
        on_batch_complete: Optional callback when the batch finishes (success or cancel).
        on_batch_file_result: Optional callback on the UI thread after each file result
            (used for dialog row updates; not an app-wide signal).
    """
    progress_q: queue.Queue[Tuple[str, Any]] = queue.Queue()
    final_results: list[BatchFileResult] = []
    cancel_event = threading.Event()
    files = list(kym_files)
    total_files = len(files)
    if total_files == 0:
        return

    if app_context is not None:
        app_context.suppress_velocity_event_cache_sync_on_detect_events = True

    timer = None  # assigned below

    def _clear_batch_suppress() -> None:
        if app_context is not None:
            app_context.suppress_velocity_event_cache_sync_on_detect_events = False

    def _drain_queue() -> None:
        nonlocal timer
        while True:
            try:
                tag, payload = progress_q.get_nowait()
            except queue.Empty:
                break

            if tag == "overall":
                completed, total = payload
                pct = (completed / total) if total else 0.0
                overall_task.set_progress(float(pct), f"{completed}/{total} files")
            elif tag == "per_file":
                per_file_task.set_progress(1.0, str(payload))
            elif tag == "file_result":
                if on_batch_file_result is not None:
                    try:
                        on_batch_file_result(payload)
                    except Exception:
                        logger.exception("on_batch_file_result failed")
            elif tag == "file_done":
                kym_file = payload
                if on_file_complete:
                    try:
                        on_file_complete(kym_file)
                    except Exception:
                        logger.exception("on_file_complete failed")
            elif tag == "finalize_cache":
                ok_files: list[KymImage] = payload
                try:
                    for kf in ok_files:
                        try:
                            image_list.update_velocity_event_cache_only(kf)
                        except Exception:
                            logger.exception(
                                "update_velocity_event_cache_only failed in batch finalize for %s",
                                getattr(kf, "path", None),
                            )
                    if on_finalize_batch_velocity_cache is not None:
                        try:
                            on_finalize_batch_velocity_cache(bool(ok_files))
                        except Exception:
                            logger.exception("on_finalize_batch_velocity_cache failed")
                finally:
                    _clear_batch_suppress()
            elif tag == "done":
                overall_task.message = "Done"
                per_file_task.message = "Done"
                overall_task.mark_finished()
                per_file_task.mark_finished()
                if on_batch_complete:
                    try:
                        on_batch_complete(True, list(final_results))
                    except Exception:
                        logger.exception("on_batch_complete failed")
                if timer is not None:
                    timer.cancel()
            elif tag == "cancelled":
                overall_task.message = "Cancelled"
                per_file_task.message = "Cancelled"
                overall_task.mark_finished()
                per_file_task.mark_finished()
                if on_batch_complete:
                    try:
                        on_batch_complete(False, list(final_results))
                    except Exception:
                        logger.exception("on_batch_complete failed")
                if timer is not None:
                    timer.cancel()
            elif tag == "error":
                _clear_batch_suppress()
                overall_task.message = f"Error: {payload}"
                per_file_task.message = f"Error: {payload}"
                overall_task.mark_finished()
                per_file_task.mark_finished()
                if on_batch_complete:
                    try:
                        on_batch_complete(False, list(final_results))
                    except Exception:
                        logger.exception("on_batch_complete failed")
                if timer is not None:
                    timer.cancel()
            else:
                logger.warning("Unknown batch kym-event worker message: %r", (tag, payload))

    timer = ui.timer(0.1, _drain_queue)

    def _worker() -> None:
        try:
            progress_q.put(("overall", (0, total_files)))
            strategy = KymEventBatchStrategy(
                roi_mode=roi_mode,
                roi_id=roi_id,
                channel=channel,
                baseline_drop_params=baseline_drop_params,
                nan_gap_params=nan_gap_params,
                zero_gap_params=zero_gap_params,
            )
            batch = KymAnalysisBatch(
                files,
                strategy,
                max_parallel_files=max_parallel_files,
            )
            completed_lock = threading.Lock()
            completed = 0

            def on_file(r: BatchFileResult) -> None:
                nonlocal completed
                file_name = (
                    r.kym_image.path.name
                    if getattr(r.kym_image, "path", None) is not None
                    else "unknown"
                )
                if r.outcome == BatchFileOutcome.OK:
                    progress_q.put(("per_file", f"{file_name}: ok"))
                    progress_q.put(("file_done", r.kym_image))
                elif r.outcome == BatchFileOutcome.SKIPPED:
                    progress_q.put(("per_file", f"{file_name}: skipped ({r.message})"))
                elif r.outcome == BatchFileOutcome.FAILED:
                    progress_q.put(("per_file", f"{file_name}: failed ({r.message})"))
                else:
                    progress_q.put(("per_file", f"{file_name}: cancelled"))
                progress_q.put(("file_result", r))
                with completed_lock:
                    completed += 1
                    progress_q.put(("overall", (completed, total_files)))

            results = batch.run(cancel_event=cancel_event, on_file_result=on_file)
            final_results[:] = results
            ok_files = [r.kym_image for r in results if r.outcome == BatchFileOutcome.OK]
            progress_q.put(("finalize_cache", ok_files))
            if cancel_event.is_set():
                progress_q.put(("cancelled", None))
            else:
                progress_q.put(("done", None))
        except Exception as exc:
            logger.exception("Batch kym-event analysis failed")
            progress_q.put(("error", repr(exc)))

    def _handle_cancel() -> None:
        cancel_event.set()

    overall_task.on_cancelled(_handle_cancel)
    per_file_task.on_cancelled(_handle_cancel)

    overall_task.set_running(True)
    overall_task.cancellable = True
    overall_task.set_progress(0.0, "Starting batch kym-event analysis")

    per_file_task.set_running(True)
    per_file_task.cancellable = True
    per_file_task.set_progress(0.0, "Waiting")

    threading.Thread(target=_worker, daemon=False).start()


def run_batch_radon_analysis(
    kym_files: Sequence[KymImage],
    image_list: KymImageList,
    per_file_task: TaskState,
    overall_task: TaskState,
    *,
    roi_mode: Literal["existing", "new_full_image"],
    roi_id: int | None,
    channel: int,
    window_size: int,
    max_parallel_files: int = 4,
    on_finalize_batch_radon_cache: Optional[Callable[[bool], None]] = None,
    on_batch_complete: Optional[Callable[[bool, list[BatchFileResult]], None]] = None,
    on_batch_file_result: Optional[Callable[[BatchFileResult], None]] = None,
) -> None:
    """Run Radon flow analysis on multiple files without blocking NiceGUI.

    Uses core :class:`KymAnalysisBatch` with :class:`RadonBatchStrategy`.
    Cache updates are deferred to a single finalize step.

    Args:
        kym_files: Files to analyze.
        image_list: List used to refresh Radon report cache after the batch.
        per_file_task: Per-file task state.
        overall_task: Overall batch task state.
        roi_mode: Existing shared ROI or new full-image ROI per file.
        roi_id: ROI id when ``roi_mode == \"existing\"``.
        channel: 1-based channel index.
        window_size: Radon window size.
        max_parallel_files: Concurrent file workers.
        on_finalize_batch_radon_cache: Optional callback after cache rebuild.
        on_batch_complete: Optional callback when the batch finishes.
        on_batch_file_result: Optional callback on the UI thread after each file result.
    """
    progress_q: queue.Queue[Tuple[str, Any]] = queue.Queue()
    cancel_event = threading.Event()
    files = list(kym_files)
    total_files = len(files)
    final_results: list[BatchFileResult] = []
    if total_files == 0:
        return

    timer = None

    def _drain_queue() -> None:
        nonlocal timer
        while True:
            try:
                tag, payload = progress_q.get_nowait()
            except queue.Empty:
                break

            if tag == "overall":
                completed, total = payload
                pct = (completed / total) if total else 0.0
                overall_task.set_progress(float(pct), f"{completed}/{total} files")
            elif tag == "per_file":
                per_file_task.set_progress(1.0, str(payload))
            elif tag == "file_result":
                if on_batch_file_result is not None:
                    try:
                        on_batch_file_result(payload)
                    except Exception:
                        logger.exception("on_batch_file_result failed")
            elif tag == "finalize_cache":
                ok_files: list[KymImage] = payload
                for kf in ok_files:
                    try:
                        image_list.update_radon_report_cache_only(kf)
                    except Exception:
                        logger.exception(
                            "update_radon_report_cache_only failed in batch finalize for %s",
                            getattr(kf, "path", None),
                        )
                if on_finalize_batch_radon_cache is not None:
                    try:
                        on_finalize_batch_radon_cache(bool(ok_files))
                    except Exception:
                        logger.exception("on_finalize_batch_radon_cache failed")
            elif tag == "done":
                overall_task.message = "Done"
                per_file_task.message = "Done"
                overall_task.mark_finished()
                per_file_task.mark_finished()
                if on_batch_complete:
                    try:
                        on_batch_complete(True, list(final_results))
                    except Exception:
                        logger.exception("on_batch_complete failed")
                if timer is not None:
                    timer.cancel()
            elif tag == "cancelled":
                overall_task.message = "Cancelled"
                per_file_task.message = "Cancelled"
                overall_task.mark_finished()
                per_file_task.mark_finished()
                if on_batch_complete:
                    try:
                        on_batch_complete(False, list(final_results))
                    except Exception:
                        logger.exception("on_batch_complete failed")
                if timer is not None:
                    timer.cancel()
            elif tag == "error":
                overall_task.message = f"Error: {payload}"
                per_file_task.message = f"Error: {payload}"
                overall_task.mark_finished()
                per_file_task.mark_finished()
                if on_batch_complete:
                    try:
                        on_batch_complete(False, list(final_results))
                    except Exception:
                        logger.exception("on_batch_complete failed")
                if timer is not None:
                    timer.cancel()

    timer = ui.timer(0.1, _drain_queue)

    def _worker() -> None:
        try:
            progress_q.put(("overall", (0, total_files)))
            strategy = RadonBatchStrategy(
                roi_mode=roi_mode,
                roi_id=roi_id,
                channel=channel,
                window_size=window_size,
            )
            batch = KymAnalysisBatch(files, strategy, max_parallel_files=max_parallel_files)
            completed_lock = threading.Lock()
            completed = 0

            def on_file(r: BatchFileResult) -> None:
                nonlocal completed
                file_name = (
                    r.kym_image.path.name
                    if getattr(r.kym_image, "path", None) is not None
                    else "unknown"
                )
                if r.outcome == BatchFileOutcome.OK:
                    progress_q.put(("per_file", f"{file_name}: ok"))
                elif r.outcome == BatchFileOutcome.SKIPPED:
                    progress_q.put(("per_file", f"{file_name}: skipped ({r.message})"))
                elif r.outcome == BatchFileOutcome.FAILED:
                    progress_q.put(("per_file", f"{file_name}: failed ({r.message})"))
                else:
                    progress_q.put(("per_file", f"{file_name}: cancelled"))
                progress_q.put(("file_result", r))
                with completed_lock:
                    completed += 1
                    progress_q.put(("overall", (completed, total_files)))

            results = batch.run(cancel_event=cancel_event, on_file_result=on_file)
            final_results[:] = results
            ok_files = [r.kym_image for r in results if r.outcome == BatchFileOutcome.OK]
            progress_q.put(("finalize_cache", ok_files))
            if cancel_event.is_set():
                progress_q.put(("cancelled", None))
            else:
                progress_q.put(("done", None))
        except Exception as exc:
            logger.exception("Batch Radon analysis failed")
            progress_q.put(("error", repr(exc)))

    def _handle_cancel() -> None:
        cancel_event.set()

    overall_task.on_cancelled(_handle_cancel)
    per_file_task.on_cancelled(_handle_cancel)

    overall_task.set_running(True)
    overall_task.cancellable = True
    overall_task.set_progress(0.0, "Starting batch Radon analysis")
    per_file_task.set_running(True)
    per_file_task.cancellable = True
    per_file_task.set_progress(0.0, "Waiting")
    threading.Thread(target=_worker, daemon=False).start()

