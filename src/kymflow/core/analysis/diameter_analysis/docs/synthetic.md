# Synthetic Intensity Model

## Core model
Synthetic generation builds an ideal vessel-like image in float space and applies a count-domain realism pipeline.

- `baseline_counts`: constant offset added everywhere (camera offset + autofluorescence).
- `signal_peak_counts`: target vessel signal amplitude above baseline in counts.
- `output_dtype` controls final representation:
  - `float32` / `float64`: normalized from count-domain model by `max_counts`.
  - `uint16`: quantized counts with optional clipping.
- `effective_bits` defines `max_counts = 2**effective_bits - 1` (11-bit default => 2047).

## Noise and artifact order
Applied in this order:
1. baseline offset
2. background drift (`bg_drift_amp_counts`, `bg_drift_period_lines`)
3. fixed pattern column noise (`fixed_pattern_col_sigma_counts`)
4. additive Gaussian background noise (`bg_gaussian_sigma_counts` + optional `bg_gaussian_sigma_frac * signal_peak_counts`)
5. multiplicative speckle on signal component (`speckle_sigma_frac`)
6. bright-band additive artifact (`bright_band_*`)
7. final clipping and dtype conversion

## Bright band artifact
- Implemented as additive-in-counts near a fixed x-location.
- If `bright_band_saturate=True` and clipping is enabled, the band region is clamped to `max_counts`.

## Recommended 11-bit starting ranges
- `effective_bits=11`
- `baseline_counts`: 100-500
- `signal_peak_counts`: 600-1600
- `bg_gaussian_sigma_counts`: 3-40
- `bg_drift_amp_counts`: 0-80
- `fixed_pattern_col_sigma_counts`: 0-15
- `speckle_sigma_frac`: 0.0-0.25
- `wall_jitter_px`: 0.0-1.5
- `bright_band_amplitude_counts`: 200-2500
