# flow_backend.py

from __future__ import annotations

import math
import os
import time
from typing import Callable, Optional, Tuple, Any

import numpy as np
from multiprocessing import Pool
from skimage.transform import radon


class FlowCancelled(Exception):
    """Raised when analysis is cancelled by the caller."""
    pass


def radon_worker(
    data_window: np.ndarray,
    angles: np.ndarray,
    angles_fine: np.ndarray,
) -> Tuple[float, np.ndarray]:
    """
    Multiprocessing worker to calculate flow for a single time window.

    Args:
        data_window:
            2D numpy array (time, space) for this window slice.
            time axis = 0, space axis = 1.
        angles:
            1D array of coarse angles (degrees).
        angles_fine:
            1D array of fine angle offsets (degrees), typically small around 0.

    Returns:
        worker_theta:
            Best angle (float, in degrees) for this window.
        worker_spread_matrix_fine:
            1D array of variance values for each fine angle.
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
    start_pixel: Optional[int] = None,
    stop_pixel: Optional[int] = None,
    *,
    verbose: bool = False,
    progress_callback: Optional[Callable[[int, int], Any]] = None,
    progress_every: int = 1,
    is_cancelled: Optional[Callable[[], bool]] = None,
    use_multiprocessing: bool = True,
    processes: Optional[int] = None,
):
    """
    Analyze a blood-flow kymograph using Radon transforms.

    Data convention:
        data is a 2D numpy array with shape (time, space),
        where:
            - axis 0 (index 0) is time (aka 'lines', 'line scans')
            - axis 1 (index 1) is space (aka 'pixels')

    Algorithm (same as your original mpAnalyzeFlow):
        - Use a sliding window along the time axis.
        - For each window, run a coarse Radon transform over 0..179 degrees.
        - Find the angle that maximizes the variance in Radon space.
        - Refine around that angle with a fine grid (e.g., ±2 degrees, 0.25 step).
        - Return best angles and associated fine spread.

    Args:
        data:
            2D numpy array (time, space).
        windowsize:
            Number of time lines per window (must be multiple of 4 given stepsize).
        start_pixel:
            Start index in 'space' dimension (axis 1), inclusive.
        stop_pixel:
            Stop index in 'space' dimension (axis 1), exclusive.
        verbose:
            If True, prints basic timing and shape info to stdout.
        progress_callback:
            Optional callable (completed, total_windows).
        progress_every:
            Emit progress every N completed windows.
        is_cancelled:
            Optional callable returning True if computation should be cancelled.
        use_multiprocessing:
            If True, uses multiprocessing.Pool; otherwise runs in a single process.
        processes:
            Optional number of worker processes. Default: cpu_count() - 1 (min 1).

    Returns:
        thetas:
            1D array (nsteps,) of best angle (degrees) per time window.
        the_t:
            1D array (nsteps,) of the center time index for each window.
        spread_matrix_fine:
            2D array (nsteps, len(angles_fine)) of fine variance values.

    Raises:
        FlowCancelled:
            If is_cancelled() returns True during processing.
    """
    start_sec = time.time()

    if data.ndim != 2:
        raise ValueError(f"data must be 2D (time, space); got shape {data.shape}")

    # time axis = 0, space axis = 1
    n_time = data.shape[0]
    n_space = data.shape[1]

    stepsize = int(0.25 * windowsize)
    if stepsize <= 0:
        raise ValueError(f"windowsize too small to compute stepsize: {windowsize}")

    nsteps = math.floor(n_time / stepsize) - 3
    if nsteps <= 0:
        raise ValueError(
            f"Invalid nsteps={nsteps}. Check windowsize={windowsize} and data.shape={data.shape}"
        )

    if start_pixel is None:
        start_pixel = 0
    if stop_pixel is None:
        stop_pixel = n_space

    # Coarse and fine angle grids (degrees)
    angles = np.arange(180, dtype=np.float32)  # 0..179 degrees
    fine_step = 0.25
    angles_fine = np.arange(-2.0, 2.0 + fine_step, fine_step, dtype=np.float32)

    # Outputs
    thetas = np.zeros(nsteps, dtype=np.float32)
    the_t = np.ones(nsteps, dtype=np.float32) * np.nan
    spread_matrix_fine = np.zeros((nsteps, len(angles_fine)), dtype=np.float32)

    if verbose:
        print(f"data shape (time, space): {data.shape}")
        print(f"  windowsize: {windowsize}, stepsize: {stepsize}")
        print(f"  n_time: {n_time}, n_space: {n_space}, nsteps: {nsteps}")
        print(f"  start_pixel: {start_pixel}, stop_pixel: {stop_pixel}")

    completed = 0
    last_emit = 0

    def cancelled() -> bool:
        return bool(is_cancelled and is_cancelled())

    def maybe_progress():
        nonlocal last_emit, completed
        if progress_callback is None:
            return
        if (completed - last_emit) >= max(1, progress_every):
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
                    raise FlowCancelled("Flow analysis cancelled before submitting all windows.")

                # Center time index for this window
                the_t[k] = 1 + k * stepsize + windowsize / 2.0

                t_start = k * stepsize
                t_stop = k * stepsize + windowsize
                data_window = data[t_start:t_stop, start_pixel:stop_pixel]

                params = (data_window, angles, angles_fine)
                result = pool.apply_async(radon_worker, params)
                result_objs.append(result)

            # Collect results
            for k, result in enumerate(result_objs):
                if cancelled():
                    pool.terminate()
                    pool.join()
                    raise FlowCancelled("Flow analysis cancelled while processing windows.")

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

            the_t[k] = 1 + k * stepsize + windowsize / 2.0

            t_start = k * stepsize
            t_stop = k * stepsize + windowsize
            data_window = data[t_start:t_stop, start_pixel:stop_pixel]

            worker_theta, worker_spread_fine = radon_worker(data_window, angles, angles_fine)
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
