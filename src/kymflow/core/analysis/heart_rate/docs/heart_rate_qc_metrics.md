# Heart Rate QC Metrics

This module reports quality metrics per method (`lombscargle`, `welch`) for each HR estimate.

## Metrics

- `snr`:
  - Peak-to-median ratio in the analysis band.
  - Higher is generally more confident.

- `edge_flag` (`bool`):
  - `True` when detected `f_peak` is near the analysis band edge.
  - Edge margin is:
    - configured via `edge_margin_hz`, or
    - computed as `max(0.2, 0.05 * (hi - lo))` when unset.

- `edge_hz_distance` (`float | None`):
  - Distance from `f_peak` to nearest band edge in Hz.
  - Smaller values indicate higher edge-risk.

- `band_concentration` (`float | None`):
  - Fraction of band power within `|f - f_peak| <= peak_half_width_hz`.
  - Near 1.0 means strongly concentrated peak; lower means broader/noisier distribution.

## Where metrics appear

- `HeartRateEstimate` (core estimate object)
- `HeartRateResults.to_dict()` in `heart_rate_pipeline.py`
- `HeartRateAnalysis.getSummaryDict()` per-roi method payloads

## Interpretation guidance

- Prefer estimates with:
  - higher `snr`
  - `edge_flag == False`
  - moderate-to-high `band_concentration`
- Treat edge-flagged estimates as lower trust, especially when both methods disagree.
