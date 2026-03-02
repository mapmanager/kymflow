#!/usr/bin/env python3
"""
run_heart_rate_examples.py

Standalone demo script for the heart-rate-from-velocity pipeline.

ASSUMPTION (per request)
------------------------
This script lives in the *same folder* as:
  - heart_rate_analysis.py
  - heart_rate_plots.py

So imports below assume sibling modules (no parent package).

What this script does
---------------------
For each provided CSV file:
  1) Load the CSV into a pandas DataFrame.
  2) Select one explicit ROI_ID and extract time/velocity.
  3) Run the complete HR analysis pipeline:
       - Global HR estimate (Lomb–Scargle and Welch)
       - Segment-based HR estimates
  4) Demonstrate all plotting helpers:
       - Overview plot (raw, cleaned, interpolated, bandpassed)
       - Welch PSD plot (peak highlighted)
       - Lomb–Scargle periodogram plot (peak highlighted)
       - Segment HR estimates vs time

How to run
----------
python run_heart_rate_examples_fixed2.py

This runner uses hard-coded `DEFAULT_FILES` and dataclass defaults (no CLI parsing).

Notes / knobs you may want to change
------------------------------------
- Column names:
    This script expects 'time' and 'velocity' columns (your standard format).
    If your CSV uses different column names, edit the constants near the top.

- ROI handling:
    CSVs may contain multiple roi_id values. This runner requires an explicit `ROI_ID`
    constant and validates it exists before analysis.

- HR band:
    The plotting defaults use HRPlotConfig(bpm_band=(240, 600)) which corresponds to 4–10 Hz.
    Adjust BPM_BAND to match physiology and your data quality.

- Outliers / gaps:
    The analysis module uses robust winsorization (MAD clipping) and can interpolate over small NaN gaps.
"""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

import numpy as np

from matplotlib import pyplot as mpl
import matplotlib.pyplot as plt

from heart_rate_pipeline import HeartRateAnalysis
from heart_rate_plots import (
    HRPlotConfig,
    plot_velocity_hr_overview,
    plot_hr_psd_welch,
    plot_hr_periodogram_lombscargle,
    plot_hr_segment_series,
)

# --------------------------
# User-editable defaults
# --------------------------
TIME_COL = "time"
VEL_COL = "velocity"
ROI_COL = "roi_id"
ROI_ID: int = 1

# Physiologically-plausible band for anesthetized mouse (you can tune this)
BPM_BAND = (240.0, 600.0)  # 4–10 Hz

DEFAULT_FILES = [
    "20251014_A98_0002_kymanalysis.csv",
    "20251014_A98_0003_kymanalysis.csv",
    "20251014_A98_0004_kymanalysis.csv",
]

DEFAULT_FILES = [
    '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline/20251014/flow-analysis/20251014_A98_0002_kymanalysis.csv',
    '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline/20251014/flow-analysis/20251014_A98_0003_kymanalysis.csv',
    '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline/20251014/flow-analysis/20251014_A98_0004_kymanalysis.csv',
    '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline/20251014/flow-analysis/20251014_A98_0005_kymanalysis.csv',
    # '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline/20251014/flow-analysis/20251014_A98_0006_kymanalysis.csv',
    # '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline/20251014/flow-analysis/20251014_A98_0007_kymanalysis.csv',
    # '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline/20251014/flow-analysis/20251014_A98_0008_kymanalysis.csv',
    # '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline/20251014/flow-analysis/20251014_A98_0009_kymanalysis.csv',
    # '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline/20251014/flow-analysis/20251014_A98_0010_kymanalysis.csv',

]


def run_one_file(csv_path: Path, *, cfg: HRPlotConfig) -> None:
    """Run analysis + plots for a single CSV."""
    print("\n" + "=" * 80)
    print(f"FILE: {csv_path}")
    analysis = HeartRateAnalysis.from_csv(
        csv_path,
        time_col=TIME_COL,
        vel_col=VEL_COL,
        roi_col=ROI_COL,
    )
    if ROI_ID not in analysis.roi_ids:
        raise ValueError(
            f"Configured ROI_ID={ROI_ID} is not present in {csv_path.name}. "
            f"Available roi_ids={analysis.roi_ids}"
        )
    roi_id = int(ROI_ID)
    print(f"  selected roi_id: {roi_id}")
    roi_results = analysis.run_roi(roi_id, cfg=cfg)
    mini_summary = analysis.get_roi_summary(roi_id, minimal="mini")
    print("\n[Summary] Mini per-ROI summary")
    pprint(mini_summary)

    t, v = analysis.get_time_velocity(roi_id)

    print(f"  samples: {len(t)}")
    print(f"  time range: {np.nanmin(t):.6f} .. {np.nanmax(t):.6f} s")
    n_valid = int(np.sum(np.isfinite(v)))
    print(f"  velocity finite: {n_valid}/{len(v)} ({100.0*n_valid/len(v):.1f}%)")

    # --------------------------
    # Analysis: global HR (run both methods every time)
    # --------------------------
    print("\n[Analysis] Global HR estimates")
    lomb_result = analysis.get_roi_results(roi_id).lomb
    welch_result = analysis.get_roi_results(roi_id).welch
    dbg_ls = {} if lomb_result is None else lomb_result.debug
    dbg_welch = {} if welch_result is None else welch_result.debug

    if lomb_result is None or lomb_result.bpm is None:
        reason = "not available" if lomb_result is None else (lomb_result.reason or "not available")
        print(f"  Lomb–Scargle: None ({reason})")
    else:
        print(
            "  Lomb–Scargle: "
            f"{lomb_result.bpm:.1f} bpm  (f={lomb_result.f_hz:.3f} Hz, snr={lomb_result.snr:.2f}, "
            f"edge={lomb_result.edge_flag}, bc={lomb_result.band_concentration})"
        )
    if welch_result is None or welch_result.bpm is None:
        reason = "not available" if welch_result is None else (welch_result.reason or "not available")
        print(f"  Welch:         None ({reason})")
    else:
        print(
            f"  Welch:         {welch_result.bpm:.1f} bpm  "
            f"(f={welch_result.f_hz:.3f} Hz, snr={welch_result.snr:.2f}, "
            f"edge={welch_result.edge_flag}, bc={welch_result.band_concentration})"
        )
    if roi_results.agreement is not None:
        print(
            f"  Agreement:     Δbpm={roi_results.agreement['delta_bpm']:+.1f}, "
            f"ΔHz={roi_results.agreement['delta_hz']:+.3f}"
        )

    # --------------------------
    # Analysis: segment HR estimates
    # --------------------------
    if cfg.do_segments:
        print("\n[Analysis] Segment-based HR estimates")
        seg_data = roi_results.segments
        if seg_data is None:
            print("  segments unavailable")
        else:
            seg_bpm = np.asarray(seg_data.get("bpm", []), dtype=float)
            seg_snr = np.asarray(seg_data.get("snr", []), dtype=float)
            print(f"  windows: {seg_bpm.size}")
            if np.any(np.isfinite(seg_bpm)):
                print(f"  bpm range: {np.nanmin(seg_bpm):.1f} .. {np.nanmax(seg_bpm):.1f}")
            if np.any(np.isfinite(seg_snr)):
                print(f"  median snr: {np.nanmedian(seg_snr):.2f}")

    # --------------------------
    # Plotting: demonstrate all plotting helpers
    # --------------------------
    # print("\n[Plots] Showing plots (close the figure windows to continue)...")

    fig, axs = mpl.subplots(3, 1, figsize=(10, 6))

    # 1) Overview plot (raw -> winsorized -> interpolated -> bandpassed)
    plot_velocity_hr_overview(
        t,
        v,
        cfg=cfg,
        title=f"{csv_path.stem} | HR overview",
        ax=axs[0],
    )

    # 2) Welch PSD plot (only if Welch estimate/debug payload is available)
    if (welch_result is not None) and (welch_result.bpm is not None) and ("f" in dbg_welch) and ("Pxx" in dbg_welch):
        try:
            plot_hr_psd_welch(
                t,
                v,
                cfg=cfg,
                title=f"{csv_path.stem} | Welch PSD",
                ax=axs[1],
            )
        except Exception as e:
            print(f"  Welch PSD plot skipped: {e}")
            axs[1].set_axis_off()
            axs[1].text(0.5, 0.5, "Welch plot unavailable", ha="center", va="center")
    else:
        if welch_result is None or welch_result.bpm is None:
            print("  Welch PSD plot skipped: Welch estimate unavailable.")
        else:
            print("  Welch PSD plot skipped: Welch debug payload missing.")
        axs[1].set_axis_off()
        axs[1].text(0.5, 0.5, "Welch plot unavailable", ha="center", va="center")

    # 3) Lomb–Scargle periodogram plot (if Lomb estimate/debug payload is available)
    if (lomb_result is not None) and (lomb_result.bpm is not None) and ("f_grid" in dbg_ls) and ("power" in dbg_ls):
        try:
            plot_hr_periodogram_lombscargle(
                t,
                v,
                cfg=cfg,
                title=f"{csv_path.stem} | Lomb–Scargle",
                ax=axs[2],
            )
        except Exception as e:
            print(f"  Lomb–Scargle plot skipped: {e}")
            axs[2].set_axis_off()
            axs[2].text(0.5, 0.5, "Lomb plot unavailable", ha="center", va="center")
    else:
        if lomb_result is None or lomb_result.bpm is None:
            print("  Lomb–Scargle plot skipped: Lomb estimate unavailable.")
        else:
            print("  Lomb–Scargle plot skipped: Lomb debug payload missing.")
        axs[2].set_axis_off()
        axs[2].text(0.5, 0.5, "Lomb plot unavailable", ha="center", va="center")

    plt.tight_layout()
    plt.show()

    if cfg.do_segments:
        seg_data = roi_results.segments
        if seg_data is None:
            print("  Segment HR plot skipped: no segment data.")
        else:
            fig_seg, ax_seg = mpl.subplots(1, 1, figsize=(10, 3))
            plot_hr_segment_series(
                seg_data.get("t_center", []),
                seg_data.get("bpm", []),
                title=f"{csv_path.stem} | segment HR series",
                ax=ax_seg,
            )
            plt.tight_layout()
            plt.show()


def main() -> None:
    cfg = HRPlotConfig()
    csv_paths = [Path(p) for p in DEFAULT_FILES]

    # Resolve relative paths against current working directory (where you run the script)
    csv_paths = [p.expanduser().resolve() for p in csv_paths]

    for p in csv_paths:
        if not p.exists():
            raise FileNotFoundError(f"CSV not found: {p}")
        run_one_file(p, cfg=cfg)

        break

    print("\nDone.")


if __name__ == "__main__":
    main()
