"""Threaded helpers for running analysis routines without blocking the GUI.

This module provides functions to run flow analysis in background threads,
with progress tracking and cancellation support through TaskState objects.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional, Sequence

from .kym_file import KymFile
from .kym_flow_radon_gpt import FlowCancelled
from .state import TaskState


def run_flow_analysis(
    kym_file: KymFile,
    task_state: TaskState,
    *,
    window_size: int = 16,
    start_pixel: Optional[int] = None,
    stop_pixel: Optional[int] = None,
    on_result: Optional[Callable[[dict], None]] = None,
) -> None:
    """Run Radon flow analysis in a background thread.
    
    Launches the analysis in a daemon thread to avoid blocking the GUI.
    Progress updates and cancellation are handled through the task_state object.
    
    Args:
        kym_file: KymFile instance to analyze.
        task_state: TaskState object for progress tracking and cancellation.
        window_size: Number of time lines per analysis window. Defaults to 16.
        start_pixel: Start index in space dimension (inclusive). If None, uses 0.
        stop_pixel: Stop index in space dimension (exclusive). If None, uses
            full width.
        on_result: Optional callback function called when analysis completes
            successfully. Receives a boolean indicating success.
    """
    cancel_event = threading.Event()

    def _worker() -> None:
        task_state.running = True
        task_state.cancellable = True
        task_state.set_progress(0.0, "Starting analysis")

        def progress_cb(completed: int, total: int) -> None:
            if total:
                pct = max(0.0, min(1.0, completed / total))
            else:
                pct = 0.0
            pct = round(pct, 1)
            task_state.set_progress(pct, f"{completed}/{total} windows")

        try:
            payload = kym_file.analyze_flow(
                window_size,
                start_pixel=start_pixel,
                stop_pixel=stop_pixel,
                progress_callback=progress_cb,
                is_cancelled=cancel_event.is_set,
            )
        except FlowCancelled:
            task_state.message = "Cancelled"
        except Exception as exc:  # pragma: no cover - surfaced to UI
            task_state.message = f"Error: {exc}"
        else:
            task_state.message = "Done"
            if on_result:
                # on_result(payload)
                on_result(True)
        finally:
            task_state.running = False
            task_state.cancellable = False
            task_state.finished.emit()

    def _handle_cancel() -> None:
        cancel_event.set()

    # Ensure multiple runs do not accumulate duplicate slots
    try:
        task_state.cancelled.disconnect(_handle_cancel)
    except Exception:
        pass
    task_state.cancelled.connect(_handle_cancel)

    # Mark running immediately so UI can react before the thread fully starts
    task_state.running = True
    task_state.cancellable = True
    threading.Thread(target=_worker, daemon=True).start()


def run_batch_flow_analysis(
    kym_files: Sequence[KymFile],
    per_file_task: TaskState,
    overall_task: TaskState,
    *,
    window_size: int = 16,
    start_pixel: Optional[int] = None,
    stop_pixel: Optional[int] = None,
    on_file_complete: Optional[Callable[[KymFile], None]] = None,
    on_batch_complete: Optional[Callable[[bool], None]] = None,
) -> None:
    """Run flow analysis sequentially for multiple files in a background thread.
    
    Processes files one at a time in a daemon thread, with progress tracking
    for both individual files and the overall batch. Supports cancellation
    at any point.
    
    Args:
        kym_files: Sequence of KymFile instances to analyze.
        per_file_task: TaskState for tracking progress of the current file.
        overall_task: TaskState for tracking overall batch progress.
        window_size: Number of time lines per analysis window. Defaults to 16.
        start_pixel: Start index in space dimension (inclusive). If None, uses 0.
        stop_pixel: Stop index in space dimension (exclusive). If None, uses
            full width.
        on_file_complete: Optional callback called after each file completes
            analysis. Receives the KymFile that was just analyzed.
        on_batch_complete: Optional callback called when the entire batch
            completes. Receives a boolean indicating if the batch was cancelled.
    """
    cancel_event = threading.Event()
    files = list(kym_files)
    total_files = len(files)
    if total_files == 0:
        return

    def _handle_cancel() -> None:
        cancel_event.set()

    try:
        per_file_task.cancelled.disconnect(_handle_cancel)
    except Exception:
        pass
    per_file_task.cancelled.connect(_handle_cancel)

    def _worker() -> None:
        cancelled = False
        per_file_task.running = True
        per_file_task.cancellable = True
        overall_task.running = True
        overall_task.cancellable = False
        overall_task.set_progress(0.0, f"0/{total_files} files")

        for index, kf in enumerate(files, start=1):
            if cancel_event.is_set():
                cancelled = True
                break

            per_file_task.set_progress(0.0, f"Starting {kf.path.name}")

            def progress_cb(completed: int, total: int) -> None:
                pct = (completed / total) if total else 0.0
                per_file_task.set_progress(pct, f"{kf.path.name}: {completed}/{total} windows")

            try:
                kf.analyze_flow(
                    window_size,
                    start_pixel=start_pixel,
                    stop_pixel=stop_pixel,
                    progress_callback=progress_cb,
                    is_cancelled=cancel_event.is_set,
                )
                # Auto-save disabled: users should explicitly save via save buttons
                # kf.save_analysis()
            except FlowCancelled:
                cancelled = True
                per_file_task.message = "Cancelled"
                break
            except Exception as exc:  # pragma: no cover - surfaced to UI
                per_file_task.message = f"Error: {exc}"
            else:
                per_file_task.message = f"Done: {kf.path.name}"
                if on_file_complete:
                    on_file_complete(kf)

            # Update overall progress (clamp to 0.0-1.0 range)
            overall_progress = max(0.0, min(1.0, index / total_files))
            overall_task.set_progress(overall_progress, f"{index}/{total_files} files")

        per_file_task.running = False
        per_file_task.cancellable = False
        per_file_task.finished.emit()

        overall_task.running = False
        overall_task.cancellable = False
        overall_task.finished.emit()

        if on_batch_complete:
            on_batch_complete(cancelled)

    threading.Thread(target=_worker, daemon=True).start()
