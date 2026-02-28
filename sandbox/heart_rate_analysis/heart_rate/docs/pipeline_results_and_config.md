# Pipeline Results And Config

`HeartRateAnalysis` stores per-ROI outputs in:

- `results_by_roi: dict[int, HeartRatePerRoiResults]`

Each `HeartRatePerRoiResults` now embeds:

- `analysis_cfg: HRAnalysisConfig`

This is the exact config used for that ROI's most recent `run_roi(...)` call.

## Why this matters

Embedding config with results prevents config/results drift and keeps each result snapshot self-contained.

## Summary API

Use:

- `getSummaryDict(compact=True)` (default)
- `getSummaryDict(compact=False)`

### Compact mode (`compact=True`)
Includes:
- global Lomb/Welch estimates
- QC fields
- agreement metrics
- `analysis_cfg`
- segment summary (`n_windows`, `n_valid_windows`, `median_bpm`, `iqr_bpm`) when segments exist

Excludes:
- raw segment arrays/time-series

### Full mode (`compact=False`)
Includes everything from compact mode plus:
- raw segment arrays (`t_center`, `bpm`, `snr`, etc.) when present

## Runner behavior

`run_heart_rate_examples_fixed2.py` prints compact summary for the selected `ROI_ID`.
