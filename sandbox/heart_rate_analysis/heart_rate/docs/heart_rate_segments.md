# Segment HR (Windowed) Analysis

Segment analysis computes heart rate on rolling time windows for QC and non-stationarity checks.

## Why use it

- Detect temporal drift or instability in HR.
- Localize artifacts to specific time ranges.
- Confirm whether global HR is representative.

## Controls

Configured via `HRPlotConfig` / `HRAnalysisConfig`:

- `do_segments` (`bool`): enable/disable segment analysis (default `False`).
- `seg_win_sec` (`float`): window length in seconds.
- `seg_step_sec` (`float`): window step in seconds.
- `seg_min_valid_frac` (`float`): minimum finite-sample fraction per window.

## Output fields

When enabled, per-roi results include `segments` with:

- `t_center`: window centers (s)
- `bpm`: per-window HR bpm (`NaN` for invalid/unresolved windows)
- `snr`: per-window SNR (`NaN` when unresolved)
- `valid_frac`: finite-data fraction per window
- `edge_flag`: edge flag per window (`1/0/NaN`)
- `band_concentration`: per-window concentration (`NaN` when unresolved)
- `method`: method label used for segment windows

## Plotting

`plot_hr_segment_series(t_center, bpm, ...)` visualizes segment HR for QC.

Normal runner behavior keeps segment analysis disabled unless `cfg.do_segments=True`.
