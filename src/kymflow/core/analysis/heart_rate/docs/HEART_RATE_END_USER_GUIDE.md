# Heart Rate Analysis Pipeline – End User Guide

## Overview

This heart rate (HR) analysis module estimates cardiac frequency from **velocity-versus-time** traces derived from kymograph analysis (e.g., Radon-based velocity extraction). It is designed for biology researchers and bioengineers working with vascular flow, electrophysiology, or imaging-derived motion signals.

The pipeline operates on a **single ROI (region of interest)** at a time and produces:

- A heart rate estimate in **Hz**
- The same estimate in **beats per minute (bpm)**
- Signal-quality metrics (how “peaky” / reliable the spectrum is)
- Cross-method agreement metrics (do two methods agree?)
- A simple status flag to aid interpretation

Two independent frequency-domain algorithms are used:

1. **Welch Power Spectral Density (PSD)**
2. **Lomb–Scargle Periodogram**

Both are applied to the same preprocessed velocity trace.

---

## What problem are we solving?

A velocity trace from a capillary often shows a pulsatile modulation caused by the heart. In the time series this can look “sin-like,” but it is typically imperfect: noisy, sometimes intermittent, and sometimes contaminated by artifacts or missing values.

We want to estimate the **dominant oscillation frequency** that corresponds to the heartbeat.

---

## Conceptual Overview of the Pipeline

**Input (per ROI):**
- `time` in seconds
- `velocity` (often in µm/s or similar; sign may depend on scan direction)

**Reality of data:**
- There may be NaNs (missing velocity)
- There may be outliers (Radon failures / ambiguous band angles)
- The pulsation may be weak or absent in some recordings
- The dominant oscillation may drift over time

**Strategy:**
- Preprocess (handle NaNs/outliers consistently)
- Estimate heart rate in the expected band (mouse under isoflurane typically ~300–500 bpm, but can vary)
- Compute quality metrics (confidence)
- Compute agreement metrics between methods
- Provide plots for interpretation

---

# Algorithm 1: Welch Power Spectral Density (PSD)

## What Welch does

Welch’s method estimates the power spectrum by:

1. Splitting the signal into overlapping segments  
2. Computing a Fourier transform in each segment  
3. Averaging the segment spectra  

This reduces spectral noise and produces a smoother estimate than a single FFT.

## What it gives you

- A frequency axis (Hz)
- Power at each frequency
- A peak frequency corresponding to the strongest oscillation
- Derived heart rate outputs:
  - `welch_hz`
  - `welch_bpm`
- A peak-quality metric:
  - `welch_snr`

## Intuition

Think of Welch as:

> “What frequency consistently carries the most energy across the recording?”

It tends to work well when:
- sampling is uniform
- the oscillation is stable in time
- the signal has enough duration

## Common pitfalls

- If the oscillation changes over time (non-stationary), Welch can blur peaks.
- If there are large missing sections, Welch can degrade unless you handle gaps carefully.
- Segment length matters: too short → noisy; too long → less responsive to changes.

---

# Algorithm 2: Lomb–Scargle Periodogram

## What Lomb–Scargle does

Lomb–Scargle estimates periodic components by fitting sinusoids across a grid of candidate frequencies. Unlike FFT-based methods, it **does not require perfectly uniform sampling**, so it can be more tolerant of irregular timing and gaps.

## What it gives you

- Frequency axis (Hz)
- Periodogram “power” at each frequency
- Peak frequency
- Derived outputs:
  - `lomb_hz`
  - `lomb_bpm`
- A peak-quality metric:
  - `lomb_snr`

## Intuition

Think of Lomb–Scargle as:

> “If I try to explain the data using a sinusoid at each frequency, which frequency best fits?”

It tends to work well when:
- the sampling is imperfect or has small gaps
- the data has fewer usable points (as long as there’s enough structure)

## Common pitfalls

- Can produce spurious peaks if the trace is dominated by noise or outliers.
- Like any spectral method, it can be misled by strong non-cardiac periodicities.

---

# Why do we use *both* algorithms?

No single spectral estimator is always best. Using both provides:

- **Cross-validation**: agreement raises confidence  
- **Diagnostics**: disagreement suggests artifacts or low quality  
- **Robustness** across datasets and acquisition conditions  

### Strengths comparison

**Welch**
- Very standard and interpretable
- Good when signal is stationary and sampling is uniform
- Usually stable for longer recordings

**Lomb–Scargle**
- More tolerant of irregular sampling / missing points
- Can be strong when data are sparse
- Useful when FFT assumptions are imperfect

### Why agreement matters

If both methods yield similar bpm values, you can be more confident the detected peak is physiological. If they diverge, it often means:

- signal is too noisy
- peak is weak or ambiguous
- multiple periodicities exist
- too much missing data

---

# How to interpret output fields

Below is an end-user friendly description of the most important outputs.

## Per-method outputs (Welch)

- **welch_hz**: Peak frequency detected (Hz).
- **welch_bpm**: Heart rate in beats per minute (`welch_hz × 60`).
- **welch_snr**: Peak signal-to-noise ratio. Higher generally means a cleaner, more isolated peak.
- **welch_edge**: `True` if the best peak is at the band edge (suggests you might need a wider band).
- **welch_bc**: “Band concentration” metric: roughly how concentrated the spectral power is near the peak (higher is typically better).

## Per-method outputs (Lomb–Scargle)

- **lomb_hz**: Peak frequency detected (Hz).
- **lomb_bpm**: Heart rate in beats per minute (`lomb_hz × 60`).
- **lomb_snr**: Peak signal-to-noise ratio for Lomb.
- **lomb_edge**: `True` if the best peak is at the band edge.
- **lomb_bc**: Band concentration metric for Lomb.

## Cross-method comparison outputs

- **agree_delta_bpm**: Absolute difference between Lomb and Welch bpm estimates (if both exist).
- **agree_ok**: `True` if the difference is within a configured tolerance (good agreement), else `False`.

## General trace quality / bookkeeping outputs

- **valid_frac**: Fraction of samples that were valid / usable (non-missing) for HR estimation.  
  - Low `valid_frac` usually means: many NaNs, unstable Radon fits, or poor image conditions.
- **status**: High-level result label for quick screening (examples: `ok`, `method_disagree`, `insufficient_data`, etc., depending on your implementation).
- **status_note**: Human-readable explanation associated with `status` (always present; may be empty when status is `ok`).

---

# Practical recommendations for researchers

1. **Use plots + numbers together.** The plots often reveal what the metrics cannot.
2. **High SNR + good agreement** → usually reliable HR estimate.
3. **Disagreement** → inspect the trace; consider whether pulsation is intermittent or masked.
4. **Low valid_frac** → interpret cautiously; many failures are data-quality related.
5. **Edge peaks** → expand band limits and re-run, or mark low confidence.

---

# Summary

This pipeline provides:
- Two independent HR estimates (Welch + Lomb–Scargle)
- QC metrics (SNR, band concentration, edge flags)
- Agreement metrics between methods
- A simple status label + note to help screen many files quickly

The aim is not just “one HR number,” but an estimate *plus* enough context for a researcher to judge whether it is trustworthy.
