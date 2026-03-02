# heart_rate_plots.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import matplotlib.pyplot as plt

from heart_rate_analysis import (
    estimate_fs,
    winsorize_mad,
    detrend_finite,
    bandpass_filter,
    dominant_freq_welch,
    dominant_freq_lombscargle,
    interpolate_small_gaps,
    HeartRateEstimate,
    estimate_heart_rate_global,
)


@dataclass(frozen=True)
class HRPlotConfig:
    bpm_band: tuple[float, float] = (240.0, 600.0)
    use_abs: bool = True
    outlier_k_mad: float = 4.0
    bandpass_order: int = 3
    nperseg_sec: float = 2.0
    interp_max_gap_sec: float = 0.05
    lomb_n_freq: int = 512
    edge_margin_hz: Optional[float] = None
    peak_half_width_hz: float = 0.5
    do_segments: bool = False
    seg_win_sec: float = 6.0
    seg_step_sec: float = 1.0
    seg_min_valid_frac: float = 0.5


def _band_hz(cfg: HRPlotConfig) -> tuple[float, float]:
    lo_bpm, hi_bpm = cfg.bpm_band
    return (lo_bpm / 60.0, hi_bpm / 60.0)


def plot_velocity_hr_overview(
    time_s: Sequence[float],
    velocity: Sequence[float],
    *,
    cfg: HRPlotConfig = HRPlotConfig(),
    title: str = "",
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot raw and preprocessed velocity signals.

    Args:
        time_s: Time samples in seconds.
        velocity: Velocity samples.
        cfg: Plot/analysis configuration.
        title: Optional plot title.
        ax: Optional axes target.

    Returns:
        plt.Axes: Axes containing the overview plot.
    """
    t = np.asarray(time_s, dtype=float)
    v = np.asarray(velocity, dtype=float)
    fs = estimate_fs(t)

    x0 = np.abs(v) if cfg.use_abs else v
    x0 = winsorize_mad(x0, k=cfg.outlier_k_mad)
    x0 = detrend_finite(x0)

    x = interpolate_small_gaps(t, x0, max_gap_sec=cfg.interp_max_gap_sec)
    m = np.isfinite(x)
    xf = np.full_like(x, np.nan)

    band_hz = _band_hz(cfg)
    if np.sum(m) > 10:
        xf[m] = bandpass_filter(x[m], fs, band_hz=band_hz, order=cfg.bandpass_order)

    created_ax = ax is None
    if ax is None:
        ax = plt.subplot(1, 1, 1)

    ax.plot(t, v, linewidth=0.8, label="velocity (raw)")
    ax.plot(t, x0, linewidth=1.0, label="preprocessed (winsorized+detrended)")
    ax.plot(t, x, linewidth=1.0, label=f"interp small gaps ≤{cfg.interp_max_gap_sec:.3f}s")
    ax.plot(t, xf, linewidth=1.2, label=f"bandpassed {band_hz[0]:.1f}-{band_hz[1]:.1f} Hz")
    ax.axhline(0, linewidth=0.5)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("velocity / a.u.")
    ax.set_title(title or "Velocity preprocessing for HR")
    ax.legend(loc="best")

    if created_ax:
        plt.tight_layout()
        plt.show()
    return ax


def plot_hr_psd_welch(
    time_s: Sequence[float],
    velocity: Sequence[float],
    *,
    cfg: HRPlotConfig = HRPlotConfig(),
    title: str = "",
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot Welch PSD with peak marker and QC annotation.

    Args:
        time_s: Time samples in seconds.
        velocity: Velocity samples.
        cfg: Plot/analysis configuration.
        title: Optional plot title.
        ax: Optional axes target.

    Returns:
        plt.Axes: Axes containing the Welch PSD.
    """
    t = np.asarray(time_s, dtype=float)
    v = np.asarray(velocity, dtype=float)
    fs = estimate_fs(t)

    x0 = np.abs(v) if cfg.use_abs else v
    x0 = winsorize_mad(x0, k=cfg.outlier_k_mad)
    x0 = detrend_finite(x0)
    x = interpolate_small_gaps(t, x0, max_gap_sec=cfg.interp_max_gap_sec)

    m = np.isfinite(x)
    x = x[m]
    if x.size < 256:
        raise ValueError("Not enough finite samples for Welch PSD plot.")

    band_hz = _band_hz(cfg)
    xf = bandpass_filter(x, fs, band_hz=band_hz, order=cfg.bandpass_order)
    nperseg = int(np.clip(round(fs * cfg.nperseg_sec), 128, 8192))
    f_peak, snr, f, Pxx = dominant_freq_welch(xf, fs, band_hz=band_hz, nperseg=nperseg)

    created_ax = ax is None
    if ax is None:
        ax = plt.subplot(1, 1, 1)

    ax.plot(f, Pxx, linewidth=1.0, label="Welch PSD")
    ax.axvline(f_peak, linewidth=1.0, label=f"peak {f_peak:.2f} Hz ({60*f_peak:.0f} bpm), snr={snr:.1f}")
    ax.set_xlim(0, min(np.max(f), band_hz[1] * 1.6))
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("PSD")
    ax.set_title(title or "Heart-rate PSD (Welch)")
    try:
        est, _dbg = estimate_heart_rate_global(
            t,
            v,
            bpm_band=cfg.bpm_band,
            use_abs=cfg.use_abs,
            outlier_k_mad=cfg.outlier_k_mad,
            method="welch",
            lomb_n_freq=cfg.lomb_n_freq,
            interp_max_gap_sec=cfg.interp_max_gap_sec,
            bandpass_order=cfg.bandpass_order,
            nperseg_sec=cfg.nperseg_sec,
            edge_margin_hz=cfg.edge_margin_hz,
            peak_half_width_hz=cfg.peak_half_width_hz,
        )
        if est is not None:
            qc_text = (
                f"bpm={est.bpm:.1f}\n"
                f"snr={est.snr:.2f}\n"
                f"edge={'YES' if est.edge_flag else 'no'}\n"
                f"bc={est.band_concentration if est.band_concentration is not None else float('nan'):.3f}"
            )
            ax.text(
                0.98,
                0.97,
                qc_text,
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=8,
                bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.7},
            )
    except Exception:
        pass
    ax.legend(loc="best")

    if created_ax:
        plt.tight_layout()
        plt.show()
    return ax


def plot_hr_periodogram_lombscargle(
    time_s: Sequence[float],
    velocity: Sequence[float],
    *,
    cfg: HRPlotConfig = HRPlotConfig(),
    title: str = "",
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot Lomb-Scargle periodogram with peak marker and QC annotation.

    Args:
        time_s: Time samples in seconds.
        velocity: Velocity samples.
        cfg: Plot/analysis configuration.
        title: Optional plot title.
        ax: Optional axes target.

    Returns:
        plt.Axes: Axes containing the Lomb-Scargle periodogram.
    """
    t = np.asarray(time_s, dtype=float)
    v = np.asarray(velocity, dtype=float)

    x0 = np.abs(v) if cfg.use_abs else v
    x0 = winsorize_mad(x0, k=cfg.outlier_k_mad)
    x0 = detrend_finite(x0)

    m = np.isfinite(t) & np.isfinite(x0)
    if np.sum(m) < 256:
        raise ValueError("Not enough finite samples for Lomb–Scargle plot.")

    band_hz = _band_hz(cfg)
    f_peak, snr, f_grid, power = dominant_freq_lombscargle(t[m], x0[m], band_hz=band_hz, n_freq=cfg.lomb_n_freq)

    
    created_ax = ax is None
    if ax is None:
        ax = plt.subplot(1, 1, 1)

    ax.plot(f_grid, power, linewidth=1.0, label="Lomb–Scargle")
    ax.axvline(f_peak, linewidth=1.0, label=f"peak {f_peak:.2f} Hz ({60*f_peak:.0f} bpm), snr={snr:.1f}")
    ax.set_xlim(band_hz[0]*0.8, band_hz[1]*1.2)
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("normalized power")
    ax.set_title(title or "Heart-rate periodogram (Lomb–Scargle)")
    try:
        est, _dbg = estimate_heart_rate_global(
            t,
            v,
            bpm_band=cfg.bpm_band,
            use_abs=cfg.use_abs,
            outlier_k_mad=cfg.outlier_k_mad,
            method="lombscargle",
            lomb_n_freq=cfg.lomb_n_freq,
            edge_margin_hz=cfg.edge_margin_hz,
            peak_half_width_hz=cfg.peak_half_width_hz,
        )
        if est is not None:
            qc_text = (
                f"bpm={est.bpm:.1f}\n"
                f"snr={est.snr:.2f}\n"
                f"edge={'YES' if est.edge_flag else 'no'}\n"
                f"bc={est.band_concentration if est.band_concentration is not None else float('nan'):.3f}"
            )
            ax.text(
                0.98,
                0.97,
                qc_text,
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=8,
                bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.7},
            )
    except Exception:
        pass
    ax.legend(loc="best")

    if created_ax:
        plt.tight_layout()
        plt.show()
    return ax


def plot_hr_segment_estimates(
    estimates: Sequence[HeartRateEstimate],
    *,
    title: str = "",
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot segment HR estimates over segment midpoints.

    Args:
        estimates: Sequence of segment-wise heart-rate estimates.
        title: Optional plot title.
        ax: Optional axes target.

    Returns:
        plt.Axes: Axes containing segment estimate plot.
    """
    if not estimates:
        raise ValueError("No estimates to plot.")
    t_mid = np.array([(e.t_start + e.t_end) / 2.0 for e in estimates], dtype=float)
    bpm = np.array([e.bpm for e in estimates], dtype=float)
    snr = np.array([e.snr for e in estimates], dtype=float)

    created_ax = ax is None
    if ax is None:
        plt.figure(figsize=(12, 4))
        ax = plt.subplot(1, 1, 1)
    ax.plot(t_mid, bpm, marker="o", linewidth=1.0, label="segment bpm")
    ax.set_xlabel("time (s) (segment mid)")
    ax.set_ylabel("HR (bpm)")
    ax.set_title(title or "Heart rate estimates per segment")
    ax.legend(loc="best")
    if created_ax:
        plt.tight_layout()
        plt.show()
    return ax


def plot_hr_segment_series(
    t_center: Sequence[float],
    bpm: Sequence[float],
    *,
    title: str = "",
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Plot windowed segment HR series for QC.

    Args:
        t_center: Window center times in seconds.
        bpm: Window HR values in bpm, may include NaN for invalid windows.
        title: Optional figure title.
        ax: Optional axes target.

    Returns:
        plt.Axes: Axes containing the segment HR series.
    """
    tc = np.asarray(t_center, dtype=float)
    y = np.asarray(bpm, dtype=float)
    created_ax = ax is None
    if ax is None:
        ax = plt.subplot(1, 1, 1)
    ax.plot(tc, y, marker="o", linewidth=1.0, label="segment HR (bpm)")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("HR (bpm)")
    ax.set_title(title or "Segment HR series")
    ax.legend(loc="best")
    if created_ax:
        plt.tight_layout()
        plt.show()
    return ax

def plot_summary(
    time_s: Sequence[float],
    velocity: Sequence[float],
    *,
    cfg: HRPlotConfig = HRPlotConfig(),
    title: str = "",
) -> tuple[plt.Figure, plt.Axes]:

    fig, axs = plt.subplots(3,1)

    plot_velocity_hr_overview(
        time_s,
        velocity,
        cfg=cfg,
        title=title,
        ax=axs[0],
    )
    
    plot_hr_psd_welch(
        time_s,
        velocity,
        cfg=cfg,
        title=title,
        ax=axs[1],
    )
    
    plot_hr_periodogram_lombscargle(
        time_s,
        velocity,
        cfg=cfg,
        title=title,
        ax=axs[2],
    )
    
    plt.tight_layout()  
    plt.show()
    return fig, axs

