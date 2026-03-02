# Batch Summary Schema

This document defines the minimal stable summary returned by:

- `HeartRateAnalysis.get_roi_summary(roi_id, minimal=True)`
- `HeartRateAnalysis.get_roi_summary(roi_id, minimal="mini")`

The summary is JSON-serializable and intentionally compact for high-volume runs.

## Keys

- `file`: Source file path (or `<arrays>` for array input)
- `roi_id`: ROI analyzed
- `n_total`: Number of rows for the ROI
- `n_valid`: Number of finite samples used
- `valid_frac`: `n_valid / n_total`
- `t_min`, `t_max`: ROI time bounds (seconds)

### Per-method outputs

- `lomb_bpm`, `lomb_hz`, `lomb_snr`
- `welch_bpm`, `welch_hz`, `welch_snr`

Values are `None` when a method did not produce an estimate.

### Minimal QC outputs

- `lomb_edge`, `welch_edge`: edge-flag booleans
- `lomb_bc`, `welch_bc`: band concentration values (`bc`)

### Agreement outputs

- `agree_delta_bpm`: `abs(lomb_bpm - welch_bpm)` or `None`
- `agree_ok`: boolean or `None`
  - `True` if `agree_delta_bpm <= agree_tol_bpm`

Default tolerance:

- `AGREE_TOL_BPM_DEFAULT = 30.0`

### Status outputs

- `status`: one of
  - `ok`
  - `insufficient_valid`
  - `no_peak_lomb`
  - `no_peak_welch`
  - `method_disagree`
  - `other_error`
- `status_note`: short reason string (empty when status is `ok`)

## Notes

- Raw segment series arrays are excluded from minimal summaries.
- Use full per-ROI summaries (`minimal=False` or `compact=False`) when raw segment arrays are needed.

## Mini Schema (Batch Table)

Use `get_roi_summary(..., minimal="mini")` for batch exports that need fixed, small columns.

### Required keys

- `file`: Basename only (`Path(path).name`)
- `roi_id`
- `valid_frac`
- `lomb_bpm`
- `lomb_hz`
- `lomb_snr`
- `welch_bpm`
- `welch_hz`
- `welch_snr`
- `agree_delta_bpm`
- `agree_ok`
- `status` (`HRStatus` value string)
- `status_note` (always present; empty string when there is no note)

### Not included in mini

- edge flags
- band concentration (`*_bc`)
- count/time-range fields (`n_total`, `n_valid`, `t_min`, `t_max`)
