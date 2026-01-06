"""Threaded helpers for running analysis routines without blocking the GUI.

This module provides functions to run flow analysis in background threads,
with progress tracking and cancellation support through TaskState objects.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional, Sequence

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.analysis.kym_flow_radon import FlowCancelled
from kymflow.core.state import TaskState


def run_flow_analysis(
    kym_file: KymImage,
    task_state: TaskState,
    *,
    window_size: int = 16,
    roi_id: Optional[int] = None,
    on_result: Optional[Callable[[bool], None]] = None,
) -> None:
    """Run Radon flow analysis on an ROI in a background thread.

    Launches the analysis in a daemon thread to avoid blocking the GUI.
    Progress updates and cancellation are handled through the task_state object.
    If no ROI exists or roi_id is not provided, creates a default ROI (full image bounds).

    Args:
        kym_file: KymImage instance to analyze.
        task_state: TaskState object for progress tracking and cancellation.
        window_size: Number of time lines per analysis window. Defaults to 16.
        roi_id: Identifier of the ROI to analyze. If None, creates a default ROI.
        on_result: Optional callback function called when analysis completes
            successfully. Receives a boolean indicating success.
    """
    cancel_event = threading.Event()

    def _worker() -> None:
        task_state.set_running(True)
        task_state.cancellable = True
        task_state.set_progress(0.0, "Starting analysis")

        # Determine ROI to use
        target_roi_id = roi_id
        if target_roi_id is None:
            # Get or create default ROI
            roi_ids = kym_file.rois.get_roi_ids()
            if roi_ids:
                # Use first ROI if available
                target_roi_id = roi_ids[0]
                task_state.set_progress(0.0, f"Using existing ROI {target_roi_id}")
            else:
                # Create default ROI (full image bounds)
                task_state.set_progress(0.0, "Creating default ROI")
                from kymflow.core.image_loaders.roi import RoiBounds
                shape = kym_file.img_shape
                if shape is None:
                    task_state.message = "Error: Cannot determine image shape for default ROI"
                    task_state.mark_finished()
                    return
                # For 2D images: shape is (H, W) = (dim0, dim1)
                if len(shape) == 2:
                    img_h, img_w = shape
                    bounds = RoiBounds(dim0_start=0, dim0_stop=img_h, dim1_start=0, dim1_stop=img_w)
                else:
                    # For 3D images: shape is (num_slices, H, W)
                    num_slices, img_h, img_w = shape
                    bounds = RoiBounds(dim0_start=0, dim0_stop=img_h, dim1_start=0, dim1_stop=img_w)
                new_roi = kym_file.rois.create_roi(bounds=bounds)
                target_roi_id = new_roi.id
                task_state.set_progress(0.0, f"Created ROI {target_roi_id}")

        # Verify ROI exists
        if kym_file.rois.get(target_roi_id) is None:
            task_state.message = f"Error: ROI {target_roi_id} not found"
            task_state.mark_finished()
            return

        def progress_cb(completed: int, total: int) -> None:
            if total:
                pct = max(0.0, min(1.0, completed / total))
            else:
                pct = 0.0
            pct = round(pct, 1)
            task_state.set_progress(pct, f"{completed}/{total} windows")

        try:
            kym_file.get_kym_analysis().analyze_roi(
                target_roi_id,
                window_size,
                progress_callback=progress_cb,
                is_cancelled=cancel_event.is_set,
                use_multiprocessing=True,
            )
        except FlowCancelled:
            task_state.message = "Cancelled"
        except Exception as exc:  # pragma: no cover - surfaced to UI
            task_state.message = f"Error: {exc}"
        else:
            task_state.message = "Done"
            if on_result:
                on_result(True)
        finally:
            task_state.mark_finished()

    def _handle_cancel() -> None:
        cancel_event.set()

    # Register cancel handler (replaces connect/disconnect pattern)
    task_state.on_cancelled(_handle_cancel)

    # Mark running immediately so UI can react before the thread fully starts
    task_state.set_running(True)
    task_state.cancellable = True
    threading.Thread(target=_worker, daemon=True).start()


def run_batch_flow_analysis(
    kym_files: Sequence[KymImage],
    per_file_task: TaskState,
    overall_task: TaskState,
    *,
    window_size: int = 16,
        on_file_complete: Optional[Callable[[KymImage], None]] = None,
    on_batch_complete: Optional[Callable[[bool], None]] = None,
) -> None:
    """Run flow analysis sequentially for multiple files in a background thread.

    Processes files one at a time in a daemon thread, with progress tracking
    for both individual files and the overall batch. Supports cancellation
    at any point. Creates a default ROI (full image bounds) for each file if none exists.

    Args:
        kym_files: Sequence of KymImage instances to analyze.
        per_file_task: TaskState for tracking progress of the current file.
        overall_task: TaskState for tracking overall batch progress.
        window_size: Number of time lines per analysis window. Defaults to 16.
        on_file_complete: Optional callback called after each file completes
            analysis. Receives the KymImage that was just analyzed.
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

    per_file_task.on_cancelled(_handle_cancel)

    def _worker() -> None:
        cancelled = False
        per_file_task.set_running(True)
        per_file_task.cancellable = True
        overall_task.set_running(True)
        overall_task.cancellable = False
        overall_task.set_progress(0.0, f"0/{total_files} files")

        for index, kf in enumerate(files, start=1):
            if cancel_event.is_set():
                cancelled = True
                break

            per_file_task.set_progress(0.0, f"Starting {kf.path.name}")

            # Get or create ROI for this file
            roi_ids = kf.rois.get_roi_ids()
            if roi_ids:
                roi_id = roi_ids[0]
            else:
                # Create default ROI (full image bounds)
                from kymflow.core.image_loaders.roi import RoiBounds
                shape = kf.img_shape
                if shape is None:
                    per_file_task.message = f"Error: Cannot determine image shape for {kf.path.name}"
                    continue
                # For 2D images: shape is (H, W) = (dim0, dim1)
                if len(shape) == 2:
                    img_h, img_w = shape
                    bounds = RoiBounds(dim0_start=0, dim0_stop=img_h, dim1_start=0, dim1_stop=img_w)
                else:
                    # For 3D images: shape is (num_slices, H, W)
                    num_slices, img_h, img_w = shape
                    bounds = RoiBounds(dim0_start=0, dim0_stop=img_h, dim1_start=0, dim1_stop=img_w)
                new_roi = kf.rois.create_roi(bounds=bounds)
                roi_id = new_roi.id
                per_file_task.set_progress(0.0, f"{kf.path.name}: Created ROI {roi_id}")

            def progress_cb(completed: int, total: int) -> None:
                pct = (completed / total) if total else 0.0
                per_file_task.set_progress(
                    pct, f"{kf.path.name}: {completed}/{total} windows"
                )

            try:
                kf.get_kym_analysis().analyze_roi(
                    roi_id,
                    window_size,
                    progress_callback=progress_cb,
                    is_cancelled=cancel_event.is_set,
                    use_multiprocessing=True,
                )
                # Auto-save disabled: users should explicitly save via save buttons
                # kf.get_kym_analysis().save_analysis()
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

        per_file_task.mark_finished()
        overall_task.mark_finished()

        if on_batch_complete:
            on_batch_complete(cancelled)

    threading.Thread(target=_worker, daemon=True).start()

