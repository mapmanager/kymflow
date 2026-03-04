# Detection Parameters

## Overview
`DiameterDetectionParams` configures three shared pipeline stages for both detection methods (`threshold_width`, `gradient_edges`):

1. Profile construction: choose time sampling and aggregate rows into a 1D spatial profile.
2. Edge detection: run threshold- or gradient-based left/right edge localization.
3. Optional motion gating: reject implausible frame-to-frame jumps (used with `gradient_edges`).

## Parameter Reference

| name | type | default | units | used by | description | tuning guidance | common failure modes |
|---|---|---:|---|---|---|---|---|
| `window_rows_odd` | `int` | `5` | px (time rows) | both | Number of rows aggregated per center frame to build each spatial profile. Must be odd. | Increase for stronger temporal denoising; decrease to preserve rapid dynamics. | Too noisy/jumpy traces (too small), over-smoothed transients (too large). |
| `stride` | `int` | `1` | px (time rows) | both | Step between analyzed center rows. | Increase for speed/coarser sampling; decrease for denser temporal coverage. | Missed fast events when stride too large. |
| `binning_method` | `BinningMethod` | `mean` | unitless | both | Row aggregation operator before edge detection (`mean` or `median`). | Use `median` for outlier resistance; use `mean` when subtle gradient contrast matters. | Texture/outliers dominate profile (`mean`), faint edges lost (`median`). |
| `polarity` | `Polarity` | `bright_on_dark` | unitless | both | Intensity convention prior to edge finding (`dark_on_bright` inverts profile). | Flip when vessel contrast is reversed from expectation. | Left/right edges appear inverted or implausible. |
| `diameter_method` | `DiameterMethod` | `threshold_width` | unitless | both | Selects detector backend (`threshold_width` or `gradient_edges`). | Try `gradient_edges` for robust wall gradients; try `threshold_width` when gradients lock to texture. | Systematic under/over-width, unstable edge picks. |
| `threshold_mode` | `str` | `half_max` | unitless | threshold_width | Threshold policy for threshold-based detection (`half_max` or `absolute`). | Prefer `half_max` for varying illumination; use `absolute` for fixed threshold workflows. | Width drift with changing illumination (`absolute` poorly tuned). |
| `threshold_value` | `float \| None` | `None` | intensity | threshold_width | Absolute threshold value used only when `threshold_mode='absolute'`. | Lower expands detected width; higher contracts width and suppresses weak regions. | Underestimated width (too high), false wide spans/background pickup (too low). |
| `gradient_sigma` | `float` | `1.5` | px | gradient_edges | Gaussian smoothing sigma before derivative edge extraction. | Increase to suppress noise; decrease to preserve sharp edge localization. | Texture lock-in/noise edges (too low), inner-edge picks from overblur (too high). |
| `gradient_kernel` | `str` | `central_diff` | unitless | gradient_edges | Derivative operator selection (currently only `central_diff` supported). | Keep default; alternative kernels are not enabled. | Validation errors if set to unsupported value. |
| `gradient_min_edge_strength` | `float` | `0.02` | intensity/px | gradient_edges | Minimum derivative magnitude considered a confident edge. | Increase to reject weak/ambiguous edges; decrease for faint-data sensitivity. | Excess false edges (too low), too many low-strength flags/misses (too high). |
| `max_edge_shift_um_on` | `bool` | `True` | unitless | gradient_edges | Enables left/right edge-displacement constraint. | Turn on to suppress edge jumps; turn off to inspect unconstrained raw edge traces. | Persistent edge jitter (off), true fast edge shifts clipped (on + strict threshold). |
| `max_diameter_change_um_on` | `bool` | `True` | unitless | gradient_edges | Enables per-frame diameter-change constraint. | Turn on to suppress diameter spikes; turn off to inspect unconstrained diameter dynamics. | Diameter spikes persist (off), true fast pulsatile changes clipped (on + strict threshold). |
| `max_center_shift_um_on` | `bool` | `True` | unitless | gradient_edges | Enables per-frame centerline-shift constraint. | Turn on for centerline stability; turn off to allow free center drift. | Centerline wobble (off), physiologic center drift clipped (on + strict threshold). |
| `max_edge_shift_um` | `float` | `2.0` | um | gradient_edges | Maximum allowed per-frame left/right edge displacement before rejection. | Increase if true motion gets clipped; decrease to suppress jumpy edge spikes. | Frequent edge-violation NaNs (too low), jitter leakage (too high). |
| `max_diameter_change_um` | `float` | `2.0` | um | gradient_edges | Maximum allowed per-frame diameter delta before rejection. | Increase for physiologic fast changes; decrease to suppress implausible spikes. | Pulse peaks clipped (too low), diameter spikes remain (too high). |
| `max_center_shift_um` | `float` | `2.0` | um | gradient_edges | Maximum allowed per-frame centerline displacement before rejection. | Increase for drifting vessels; decrease for stronger centerline stabilization. | Drift clipped (too low), centerline wobble persists (too high). |

## Tuning Cookbook

### Edges jumping / centerline jitter
1. Use `diameter_method="gradient_edges"`.
2. Keep relevant toggles enabled: `max_edge_shift_um_on=True`, `max_diameter_change_um_on=True`, `max_center_shift_um_on=True`.
3. Increase `gradient_sigma` modestly.
4. Tighten `max_edge_shift_um` and `max_center_shift_um`.
Trade-off: stronger constraints can suppress true rapid motion.

### False edges / background texture
1. Use `binning_method="median"`.
2. Increase `gradient_sigma` and/or `gradient_min_edge_strength`.
Trade-off: too much smoothing can blur true wall transitions.

### Missing edges / low contrast
1. Verify `polarity` first.
2. Increase `window_rows_odd` for better SNR.
3. For `gradient_edges`, lower `gradient_min_edge_strength`.
4. For `threshold_width+absolute`, lower `threshold_value`.
Trade-off: higher sensitivity may increase false positives.

### Over-smoothing / under-smoothing
- Over-smoothed (features lagged/flattened): lower `gradient_sigma` and/or `window_rows_odd`.
- Under-smoothed (noisy, unstable traces): raise `gradient_sigma` and/or `window_rows_odd`.
Trade-off: balancing temporal responsiveness vs robustness is dataset-specific.
