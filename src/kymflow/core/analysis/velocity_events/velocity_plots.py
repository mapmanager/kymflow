# src/kymflow/core/analysis/velocity_events/velocity_plots.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tifffile
from matplotlib.figure import Figure
from matplotlib.axes import Axes

from kymflow.core.analysis.velocity_events.velocity_events import (
    VelocityEvent,
    rolling_nanmedian,
    estimate_fs,
)


@dataclass(frozen=True)
class KymScaling:
    delx_um_per_px: float
    delt_s_per_line: float


def read_scaling_from_csv_first_row(csv_path: str | Path) -> KymScaling:
    """Read delx/delt from the first data row of your CSV export."""
    df = pd.read_csv(csv_path, nrows=1)
    if "delx" not in df.columns or "delt" not in df.columns:
        raise ValueError(f"CSV missing required scaling columns delx/delt: {csv_path}")
    return KymScaling(float(df.loc[0, "delx"]), float(df.loc[0, "delt"]))


def load_kym_tif(tif_path: str | Path) -> np.ndarray:
    """Load a kymograph TIFF as a 2D array shaped (time, space)."""
    img = tifffile.imread(str(tif_path))
    if img.ndim != 2:
        raise ValueError(f"Expected 2D kymograph (time, space); got shape {img.shape}")
    return img


def contrast_clip(img: np.ndarray, p_lo: float = 1.0, p_hi: float = 99.5) -> np.ndarray:
    """Percentile clip for display (returns float32)."""
    lo, hi = np.percentile(img, [p_lo, p_hi])
    return np.clip(img.astype(np.float32), lo, hi)


def _get_or_make_ax(
    ax: Optional[Axes], *, figsize: tuple[float, float]
) -> tuple[Figure, Axes, bool]:
    """Return (fig, ax, created). If ax provided, returns its fig and created=False."""
    if ax is not None:
        return ax.figure, ax, False
    fig, ax2 = plt.subplots(figsize=figsize)
    return fig, ax2, True


def plot_velocity_zoom(
    time_s: np.ndarray,
    velocity: np.ndarray,
    event: VelocityEvent,
    *,
    zoom_sec: float = 0.5,
    smooth_sec: float = 0.05,
    title: str = "",
    ax: Optional[Axes] = None,
) -> Axes:
    """Plot velocity around an event and return the matplotlib Axes.

    What is plotted
    ---------------
    - Raw velocity(t)
    - Rolling nan-median of |velocity| (window ~ smooth_sec)
    - Vertical lines for event onset (t_start) and optional peak (t_peak)

    Notes
    -----
    - This function does NOT call plt.show().
    - Caller controls display (GUI) or saving (tests).
    """
    t = np.asarray(time_s, dtype=float)
    v = np.asarray(velocity, dtype=float)

    center = event.t_peak if event.t_peak is not None else event.t_start
    m = (t >= center - zoom_sec) & (t <= center + zoom_sec)

    fs = estimate_fs(t)
    w = int(max(3, round(smooth_sec * fs))) | 1  # odd >=3
    abs_med = rolling_nanmedian(np.abs(v), w)

    fig, ax, created = _get_or_make_ax(ax, figsize=(12, 4))
    ax.plot(t[m], v[m], linewidth=1, label="velocity (raw)")
    ax.plot(t[m], abs_med[m], linewidth=2, label=f"|v| rolling median ({smooth_sec*1000:.0f} ms)")
    ax.axvline(float(event.t_start), linewidth=1, label="onset")
    if event.t_peak is not None and np.isfinite(event.t_peak):
        ax.axvline(float(event.t_peak), linewidth=1, label="peak")
    ax.axhline(0, linewidth=0.5)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("velocity")
    ax.set_title(title or f"{event.machine_type.value}: onset {event.t_start:.3f}s")
    ax.legend(loc="best")
    if created:
        fig.tight_layout()
    return ax


def plot_kym_zoom_with_event(
    img_time_space: np.ndarray,
    scaling: KymScaling,
    event: VelocityEvent,
    *,
    zoom_sec: float = 0.5,
    alpha: float = 0.6,
    title: str = "",
    span_sec_if_no_end: float = 0.20,
    ax: Optional[Axes] = None,
    # Optional: if you already computed contrast_clip(img), pass it to avoid recompute
    disp_time_space: Optional[np.ndarray] = None,
) -> Axes:
    """Plot a kymograph zoom with an event overlay and return the matplotlib Axes.

    Coordinate conventions
    ----------------------
    - Input image is shaped (time, space).
    - Plot is transposed so final axes are:
        x = time (s), y = space (µm)

    Overlay semantics
    -----------------
    - If event.t_end exists and > t_start: draw CYAN span [t_start, t_end]
    - If event.t_end is missing/invalid: draw RED span [t_start, t_start + span_sec_if_no_end]

    Notes
    -----
    - This function does NOT call plt.show().
    - Caller controls display/saving.
    """
    img = np.asarray(img_time_space)
    n_time, n_space = img.shape
    t_max = n_time * float(scaling.delt_s_per_line)
    y_max = n_space * float(scaling.delx_um_per_px)

    disp = disp_time_space if disp_time_space is not None else contrast_clip(img, 1.0, 99.5)

    center = event.t_peak if event.t_peak is not None else event.t_start
    t_lo = max(0.0, float(center) - zoom_sec)
    t_hi = min(t_max, float(center) + zoom_sec)

    i_lo = max(0, int(np.floor(t_lo / scaling.delt_s_per_line)))
    i_hi = min(n_time, int(np.ceil(t_hi / scaling.delt_s_per_line)))
    sub = disp[i_lo:i_hi, :]

    x0 = i_lo * scaling.delt_s_per_line
    x1 = i_hi * scaling.delt_s_per_line

    t_start = float(event.t_start)
    t_end = event.t_end
    if t_end is None or (not np.isfinite(t_end)) or (t_end <= t_start):
        t_end_plot = min(t_max, t_start + float(span_sec_if_no_end))
        color = "red"
        label = "event onset (fixed span)"
    else:
        t_end_plot = float(t_end)
        color = "cyan"
        label = "event (bounded)"

    fig, ax, created = _get_or_make_ax(ax, figsize=(12, 4.8))
    ax.imshow(
        sub.T,
        aspect="auto",
        origin="lower",
        extent=[x0, x1, 0.0, y_max],
    )
    ax.set_xlabel("time (s)")
    ax.set_ylabel("space (µm)")
    ax.set_title(title or f"Kym zoom ({event.machine_type.value})")
    ax.axvspan(t_start, t_end_plot, alpha=alpha, label=label, color=color)
    ax.legend(loc="best")
    if created:
        fig.tight_layout()
    return ax