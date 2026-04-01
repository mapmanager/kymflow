# heart_rate_plots_plotly.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import numpy as np

from .heart_rate_analysis import (
    estimate_fs,
    winsorize_mad,
    detrend_finite,
    bandpass_filter,
    dominant_freq_welch,
    dominant_freq_lombscargle,
    interpolate_small_gaps,
    estimate_heart_rate_global,
)


@dataclass(frozen=True)
class HRPlotlyConfig:
    """Configuration shared by Plotly heart-rate plots.

    This intentionally mirrors ``heart_rate_plots.HRPlotConfig`` so callers can
    keep one mental model across matplotlib vs Plotly.

    Attributes:
        bpm_band: (lo_bpm, hi_bpm) frequency band in beats per minute.
        use_abs: If True, analyze abs(velocity) before preprocessing.
        outlier_k_mad: Winsorization factor (k * MAD) used to clip outliers.
        bandpass_order: Butterworth bandpass order.
        nperseg_sec: Welch window length in seconds.
        interp_max_gap_sec: Max gap (sec) to linearly interpolate across small NaN gaps.
        lomb_n_freq: Number of frequency samples in Lomb–Scargle grid across bpm_band.
        edge_margin_hz: Optional margin (Hz) used by the estimator to flag edge peaks.
        peak_half_width_hz: Half-width (Hz) around peak for band-concentration QC.
    """
    bpm_band: tuple[float, float] = (240.0, 600.0)
    use_abs: bool = True
    outlier_k_mad: float = 4.0
    bandpass_order: int = 3
    nperseg_sec: float = 2.0
    interp_max_gap_sec: float = 0.05
    lomb_n_freq: int = 512
    edge_margin_hz: Optional[float] = None
    peak_half_width_hz: float = 0.5


def _band_hz(cfg: HRPlotlyConfig) -> tuple[float, float]:
    lo_bpm, hi_bpm = cfg.bpm_band
    return (lo_bpm / 60.0, hi_bpm / 60.0)


def _line_trace(x: np.ndarray, y: np.ndarray, name: str, *, width: float = 1.2) -> dict[str, Any]:
    """Return a Plotly 'scatter' trace dict in line mode."""
    return {
        "type": "scatter",
        "mode": "lines",
        "x": x.tolist(),
        "y": y.tolist(),
        "name": name,
        "line": {"width": width},
    }


def _hline_shape(y: float = 0.0) -> dict[str, Any]:
    """Return a Plotly horizontal line 'shape' at y."""
    return {
        "type": "line",
        "xref": "paper",
        "x0": 0.0,
        "x1": 1.0,
        "yref": "y",
        "y0": y,
        "y1": y,
        "line": {"width": 1},
    }


def plot_velocity_hr_overview_plotly(
    time_s: Sequence[float],
    velocity: Sequence[float],
    *,
    cfg: HRPlotlyConfig = HRPlotlyConfig(),
    title: str = "",
) -> dict[str, Any]:
    """Plot raw and preprocessed velocity signals (Plotly dict).

    This replicates ``plot_velocity_hr_overview`` (matplotlib) but returns a Plotly
    figure *dict* (not a go.Figure) so it works cleanly with NiceGUI / Jupyter.

    Preprocessing pipeline (same as analysis):
        1) optional abs()
        2) winsorize outliers via MAD
        3) detrend finite samples
        4) interpolate small NaN gaps (<= cfg.interp_max_gap_sec)
        5) bandpass filter in cfg.bpm_band (Hz band)

    Args:
        time_s: Time samples in seconds.
        velocity: Velocity samples (may include NaN).
        cfg: Plot/analysis configuration.
        title: Optional plot title.

    Returns:
        Plotly figure dict with keys: "data", "layout".
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

    data = [
        _line_trace(t, v, "velocity (raw)", width=1.0),
        _line_trace(t, x0, "preprocessed (winsorized+detrended)", width=1.2),
        _line_trace(t, x, f"interp small gaps ≤{cfg.interp_max_gap_sec:.3f}s", width=1.2),
        _line_trace(t, xf, f"bandpassed {band_hz[0]:.1f}-{band_hz[1]:.1f} Hz", width=1.6),
    ]

    layout = {
        "title": {"text": title or "Velocity preprocessing for HR"},
        "xaxis": {"title": "time (s)"},
        "yaxis": {"title": "velocity / a.u."},
        "legend": {"orientation": "h"},
        "margin": {"l": 60, "r": 20, "t": 50, "b": 50},
        "shapes": [_hline_shape(0.0)],
    }
    return {"data": data, "layout": layout}


def plot_hr_psd_welch_plotly(
    time_s: Sequence[float],
    velocity: Sequence[float],
    *,
    cfg: HRPlotlyConfig = HRPlotlyConfig(),
    title: str = "",
) -> dict[str, Any]:
    """Plot Welch PSD with peak marker and QC annotation (Plotly dict).

    Args:
        time_s: Time samples in seconds.
        velocity: Velocity samples (may include NaN).
        cfg: Plot/analysis configuration.
        title: Optional plot title.

    Returns:
        Plotly figure dict with keys: "data", "layout".

    Raises:
        ValueError: If there are not enough finite samples to compute a PSD.
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

    data = [
        _line_trace(f, Pxx, "Welch PSD", width=1.6),
    ]

    # Vertical peak marker as a shape
    shapes = [{
        "type": "line",
        "xref": "x",
        "x0": float(f_peak),
        "x1": float(f_peak),
        "yref": "paper",
        "y0": 0.0,
        "y1": 1.0,
        "line": {"width": 2},
    }]

    annotations = [{
        "xref": "x",
        "yref": "paper",
        "x": float(f_peak),
        "y": 1.02,
        "text": f"peak {float(f_peak):.2f} Hz ({60*float(f_peak):.0f} bpm), snr={float(snr):.1f}",
        "showarrow": False,
        "xanchor": "left",
        "font": {"size": 12},
    }]

    # Optional QC block from global estimator (if available)
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
            bc = est.band_concentration
            qc_text = (
                f"bpm={est.bpm:.1f}<br>"
                f"snr={est.snr:.2f}<br>"
                f"edge={'YES' if est.edge_flag else 'no'}<br>"
                f"bc={(float(bc) if bc is not None else float('nan')):.3f}"
            )
            annotations.append({
                "xref": "paper",
                "yref": "paper",
                "x": 0.98,
                "y": 0.98,
                "text": qc_text,
                "showarrow": False,
                "xanchor": "right",
                "yanchor": "top",
                "align": "right",
                "bgcolor": "rgba(255,255,255,0.75)",
                "bordercolor": "rgba(0,0,0,0.2)",
                "borderwidth": 1,
                "font": {"size": 11},
            })
    except Exception:
        pass

    layout = {
        "title": {"text": title or "Heart-rate PSD (Welch)"},
        "xaxis": {"title": "frequency (Hz)", "range": [0.0, float(min(np.max(f), band_hz[1] * 1.6))]},
        "yaxis": {"title": "PSD"},
        "margin": {"l": 70, "r": 20, "t": 60, "b": 50},
        "shapes": shapes,
        "annotations": annotations,
    }
    return {"data": data, "layout": layout}


def plot_hr_periodogram_lombscargle_plotly(
    time_s: Sequence[float],
    velocity: Sequence[float],
    *,
    cfg: HRPlotlyConfig = HRPlotlyConfig(),
    title: str = "",
) -> dict[str, Any]:
    """Plot Lomb–Scargle periodogram with peak marker and QC annotation (Plotly dict).

    Args:
        time_s: Time samples in seconds.
        velocity: Velocity samples (may include NaN).
        cfg: Plot/analysis configuration.
        title: Optional plot title.

    Returns:
        Plotly figure dict with keys: "data", "layout".

    Raises:
        ValueError: If there are not enough finite samples to compute the periodogram.
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
    f_peak, snr, f_grid, power = dominant_freq_lombscargle(
        t[m],
        x0[m],
        band_hz=band_hz,
        n_freq=cfg.lomb_n_freq,
    )

    data = [
        _line_trace(f_grid, power, "Lomb–Scargle", width=1.6),
    ]

    shapes = [{
        "type": "line",
        "xref": "x",
        "x0": float(f_peak),
        "x1": float(f_peak),
        "yref": "paper",
        "y0": 0.0,
        "y1": 1.0,
        "line": {"width": 2},
    }]

    annotations = [{
        "xref": "x",
        "yref": "paper",
        "x": float(f_peak),
        "y": 1.02,
        "text": f"peak {float(f_peak):.2f} Hz ({60*float(f_peak):.0f} bpm), snr={float(snr):.1f}",
        "showarrow": False,
        "xanchor": "left",
        "font": {"size": 12},
    }]

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
            bc = est.band_concentration
            qc_text = (
                f"bpm={est.bpm:.1f}<br>"
                f"snr={est.snr:.2f}<br>"
                f"edge={'YES' if est.edge_flag else 'no'}<br>"
                f"bc={(float(bc) if bc is not None else float('nan')):.3f}"
            )
            annotations.append({
                "xref": "paper",
                "yref": "paper",
                "x": 0.98,
                "y": 0.98,
                "text": qc_text,
                "showarrow": False,
                "xanchor": "right",
                "yanchor": "top",
                "align": "right",
                "bgcolor": "rgba(255,255,255,0.75)",
                "bordercolor": "rgba(0,0,0,0.2)",
                "borderwidth": 1,
                "font": {"size": 11},
            })
    except Exception:
        pass

    layout = {
        "title": {"text": title or "Heart-rate periodogram (Lomb–Scargle)"},
        "xaxis": {"title": "frequency (Hz)", "range": [float(band_hz[0] * 0.8), float(band_hz[1] * 1.2)]},
        "yaxis": {"title": "normalized power"},
        "margin": {"l": 70, "r": 20, "t": 60, "b": 50},
        "shapes": shapes,
        "annotations": annotations,
    }
    return {"data": data, "layout": layout}
