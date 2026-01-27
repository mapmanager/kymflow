"""Radon transform-based flow analysis for kymograph images.

This module implements a multiprocessing-capable flow analysis algorithm using
Radon transforms to detect flow direction and velocity in kymograph data.
The algorithm uses a sliding window approach with coarse and fine angle
search to efficiently determine flow angles.
"""

from __future__ import annotations

import math
import os
import time
import queue
from typing import Callable, Optional, Tuple, Any

import numpy as np
from multiprocessing import Pool
from skimage.transform import radon

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

class FlowCancelled(Exception):
    """Exception raised when flow analysis is cancelled.

    This exception is raised when the analysis is cancelled via the
    is_cancelled callback during processing.
    """

    pass


def radon_worker(
    data_window: np.ndarray,
    angles: np.ndarray,
    angles_fine: np.ndarray,
) -> Tuple[float, np.ndarray]:
    """Calculate flow angle for a single time window using Radon transforms.

    This function is designed to be used as a multiprocessing worker. It
    performs a two-stage Radon transform: first a coarse search over all
    angles, then a fine search around the best coarse angle.

    Args:
        data_window: 2D numpy array (time, space) for this window slice.
            Time axis is 0, space axis is 1. The mean is subtracted before
            processing.
        angles: 1D array of coarse angles in degrees (typically 0-179).
        angles_fine: 1D array of fine angle offsets in degrees, typically
            small values around 0 (e.g., -2 to +2 degrees in 0.25 degree steps).

    Returns:
        Tuple containing:
            - Best angle in degrees (float) for this window.
            - 1D array of variance values for each fine angle.
    """
    # Ensure float for radon + mean subtraction
    data_window = data_window.astype(np.float32, copy=False)

    # Subtract mean over entire window
    mean_val = float(np.mean(data_window))
    data_window = data_window - mean_val

    # Coarse radon transform
    # radon will return shape (len(time_projection), len(angles))
    radon_coarse = radon(data_window, theta=angles, circle=False)
    spread_coarse = np.var(radon_coarse, axis=0)  # variance per angle

    # Coarse maximum
    max_idx = int(np.argmax(spread_coarse))
    coarse_theta = float(angles[max_idx])

    # Fine search around coarse max
    fine_angles = coarse_theta + angles_fine
    radon_fine = radon(data_window, theta=fine_angles, circle=False)
    spread_fine = np.var(radon_fine, axis=0)

    fine_idx = int(np.argmax(spread_fine))
    best_theta = coarse_theta + float(angles_fine[fine_idx])

    return best_theta, spread_fine


def mp_analyze_flow(
    data: np.ndarray,
    windowsize: int,
    dim0_start: Optional[int],
    dim0_stop: Optional[int],
    dim1_start: Optional[int],
    dim1_stop: Optional[int],
    *,
    verbose: bool = False,
    progress_callback: Optional[Callable[[int, int], Any]] = None,
    progress_queue: Optional[queue.Queue] = None,
    progress_every: int = 1,
    is_cancelled: Optional[Callable[[], bool]] = None,
    use_multiprocessing: bool = True,
    processes: Optional[int] = None,
):
    """Analyze blood flow in a kymograph using Radon transforms.

    Performs a sliding window analysis along the time axis to detect flow
    direction and velocity. Uses a two-stage Radon transform approach:
    coarse search over 0-179 degrees, then fine refinement around the best
    angle.

    Data convention:
        data is a 2D numpy array with shape (time, space), where:
        - axis 0 (index 0) is time (aka 'lines', 'line scans')
        - axis 1 (index 1) is space (aka 'pixels')

    Algorithm:
        - Use a sliding window along the time axis with 25% overlap.
        - For each window, run a coarse Radon transform over 0..179 degrees.
        - Find the angle that maximizes the variance in Radon space.
        - Refine around that angle with a fine grid (±2 degrees, 0.25 step).
        - Return best angles and associated fine spread.

    Args:
        data: 2D numpy array (time, space) containing the kymograph data.
        windowsize: Number of time lines per analysis window. Must be a
            multiple of 4 (stepsize is 25% of windowsize).
        start_pixel: Start index in space dimension (axis 1), inclusive.
            If None, uses 0.
        stop_pixel: Stop index in space dimension (axis 1), exclusive.
            If None, uses full width.
        start_line: Start index in time dimension (axis 0), inclusive.
            If None, uses 0.
        stop_line: Stop index in time dimension (axis 0), exclusive.
            If None, uses full height (n_time).
        verbose: If True, prints timing and shape information to stdout.
        progress_callback: Optional callable(completed, total_windows) called
            periodically to report progress. (Deprecated for GUI usage; prefer
            progress_queue.)
        progress_queue: Optional queue to receive progress messages from the
            parent process as tuples of the form ('progress', completed, total).
            This is safe to consume from GUI/main threads.
        progress_every: Emit progress every N completed windows. Defaults to 1.
        is_cancelled: Optional callable() -> bool that returns True if
            computation should be cancelled.
        use_multiprocessing: If True, uses multiprocessing.Pool for parallel
            computation. If False, runs sequentially. Defaults to True.
        processes: Optional number of worker processes. If None, uses
            cpu_count() - 1 (minimum 1). Defaults to None.

    Returns:
        Tuple containing:
            - thetas: 1D array (nsteps,) of best angle in degrees per window.
            - the_t: 1D array (nsteps,) of center time index for each window.
            - spread_matrix_fine: 2D array (nsteps, len(angles_fine)) of
              variance values for fine angles.

    Raises:
        ValueError: If data is not 2D or windowsize is invalid.
        FlowCancelled: If is_cancelled() returns True during processing.
    """
    start_sec = time.time()

    # if data.ndim != 2:
    #     raise ValueError(f"data must be 2D (time, space); got shape {data.shape}")

    if dim0_start is None:
        dim0_start = 0
    if dim0_stop is None:
        dim0_stop = data.shape[0]
    if dim1_start is None:
        dim1_start = 0
    if dim1_stop is None:
        dim1_stop = data.shape[1]

    # time axis = 0, space axis = 1
    n_time = dim0_stop - dim0_start  # data.shape[1]
    # n_space = dim1_stop - dim1_start  # data.shape[0]

    stepsize = int(0.25 * windowsize)
    if stepsize <= 0:
        raise ValueError(f"windowsize too small to compute stepsize: {windowsize}")

    # nsteps from number of time lines in data
    nsteps = math.floor(n_time / stepsize) - 3
    if nsteps <= 0:
        raise ValueError(
            f"Invalid nsteps={nsteps}. Check windowsize={windowsize} and data.shape={data.shape}"
        )

    # Coarse and fine angle grids (degrees)
    angles = np.arange(180, dtype=np.float32)  # 0..179 degrees
    fine_step = 0.25
    angles_fine = np.arange(-2.0, 2.0 + fine_step, fine_step, dtype=np.float32)

    # Outputs
    thetas = np.zeros(nsteps, dtype=np.float32)
    the_t = np.ones(nsteps, dtype=np.float32) * np.nan
    spread_matrix_fine = np.zeros((nsteps, len(angles_fine)), dtype=np.float32)

    verbose = False
    if verbose:
        print(f"=== mp_analyze_flow data shape (space, time): {data.shape}")
        print(f"  windowsize: {windowsize}, stepsize: {stepsize}")
        # print(f"  n_time: {n_time}, n_space: {n_space}, nsteps: {nsteps}")
        print(f"  dim0_start: {dim0_start}, dim0_stop: {dim0_stop}")
        print(f"  dim1_start: {dim1_start}, dim1_stop: {dim1_stop}")

    completed = 0
    last_emit = 0

    # Emit initial progress so GUIs can show total work immediately.
    if progress_queue is not None:
        try:
            progress_queue.put(("progress", 0, nsteps))
        except Exception:
            pass

    def cancelled() -> bool:
        return bool(is_cancelled and is_cancelled())

    def maybe_progress() -> None:
        """Emit progress from the *parent process* only.

        This function is safe to call from either the main thread or a background
        thread, but it must never be invoked from within multiprocessing worker
        processes. In this module, it is only called in the parent process.
        """
        nonlocal last_emit, completed

        if (completed - last_emit) < max(1, progress_every):
            return

        # 1) Queue-based progress (recommended for GUIs)
        if progress_queue is not None:
            try:
                progress_queue.put(("progress", completed, nsteps))
            except Exception:
                # Progress must never crash analysis
                pass

        # 2) Legacy callback-based progress (OK for CLI / non-GUI)
        if progress_callback is not None:
            try:
                progress_callback(completed, nsteps)
            except Exception:
                # Swallow progress errors; they shouldn't kill the computation.
                pass

        last_emit = completed

    # --- Multiprocessing path ---
    if use_multiprocessing and nsteps > 1:
        proc_count = processes or (os.cpu_count() or 1) - 1
        proc_count = max(1, proc_count)

        with Pool(processes=proc_count) as pool:
            result_objs = []

            # Enqueue all windows
            for k in range(nsteps):
                if cancelled():
                    pool.terminate()
                    pool.join()
                    raise FlowCancelled(
                        "Flow analysis cancelled before submitting all windows."
                    )

                # Center time index for this window
                # the_t[k] = 1 + k * stepsize + windowsize / 2.0
                the_t[k] = dim0_start + (k * stepsize) + (windowsize / 2.0)

                # t_start = k * stepsize
                # t_stop = k * stepsize + windowsize
                t_start = dim0_start + (k * stepsize)
                t_stop = t_start + windowsize

                # data_window = data[t_start:t_stop, start_pixel:stop_pixel]
                data_window = data[t_start:t_stop, dim1_start:dim1_stop]

                params = (data_window, angles, angles_fine)
                result = pool.apply_async(radon_worker, params)
                result_objs.append(result)

            # Collect results
            for k, result in enumerate(result_objs):
                if cancelled():
                    pool.terminate()
                    pool.join()
                    raise FlowCancelled(
                        "Flow analysis cancelled while processing windows."
                    )

                worker_theta, worker_spread_fine = result.get()
                thetas[k] = worker_theta
                spread_matrix_fine[k, :] = worker_spread_fine

                completed += 1
                maybe_progress()

    # --- Single-process path (debug / small data) ---
    else:
        for k in range(nsteps):
            if cancelled():
                raise FlowCancelled("Flow analysis cancelled (single-process mode).")

            # the_t[k] = 1 + k * stepsize + windowsize / 2.0
            the_t[k] = dim0_start + (k * stepsize) + (windowsize / 2.0)

            # t_start = k * stepsize
            # t_stop = k * stepsize + windowsize
            t_start = dim0_start + (k * stepsize)
            t_stop = t_start + windowsize

            # data_window = data[t_start:t_stop, start_pixel:stop_pixel]
            data_window = data[t_start:t_stop, dim1_start:dim1_stop]

            worker_theta, worker_spread_fine = radon_worker(
                data_window, angles, angles_fine
            )
            thetas[k] = worker_theta
            spread_matrix_fine[k, :] = worker_spread_fine

            completed += 1
            maybe_progress()

    # Final progress update
    if progress_callback is not None:
        try:
            progress_callback(nsteps, nsteps)
        except Exception:
            pass

    if verbose:
        stop_sec = time.time()
        print(f"Flow analysis took {round(stop_sec - start_sec, 2)} seconds")

    return thetas, the_t, spread_matrix_fine
