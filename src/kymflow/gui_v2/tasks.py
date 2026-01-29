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
from typing import Callable, Optional, Sequence, Tuple, Any, Union

from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.analysis.kym_flow_radon import FlowCancelled
from kymflow.core.state import TaskState
from kymflow.core.utils.logging import get_logger

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
        on_result: Optional callback invoked on successful completion.
            Runs on the NiceGUI main loop.
    """
    # Validate roi_id early, while we still have UI context.
    if roi_id is None:
        task_state.set_running(True)
        task_state.message = "Error: ROI ID is required"
        task_state.mark_finished()
        return

    if kym_file.rois.get(roi_id) is None:
        task_state.set_running(True)
        task_state.message = f"Error: ROI {roi_id} not found"
        task_state.mark_finished()
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
                task_state.message = "Done"
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
                task_state.message = "Cancelled"
                task_state.mark_finished()
                if timer is not None:
                    timer.cancel()
            elif tag == "error":
                # ('error', 'message')
                task_state.message = f"Error: {msg[1]}"
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

            kym_file.get_kym_analysis().analyze_roi(
                roi_id,
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
                    
                    kym_file.get_kym_analysis().analyze_roi(
                        roi_id,
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

