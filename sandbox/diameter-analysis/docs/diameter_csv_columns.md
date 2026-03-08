# Diameter CSV Columns

`<kym_stem>.diameter.csv` stores numeric diameter analysis results.

- Each row corresponds to one `time_s` sample.
- `time_s` is the global kymograph time axis.
- ROI-specific columns use suffix `_roi{roi_id}` (for example, `_roi1`, `_roi2`).

## Time Axis

| Column | Units | Description |
|---|---|---|
| `time_s` | seconds | Global time axis for the kymograph. |

## Edge Positions

| Column | Units | Description |
|---|---|---|
| `left_edge_px_roi{roi_id}` | px | Left vessel edge position in pixels. |
| `right_edge_px_roi{roi_id}` | px | Right vessel edge position in pixels. |
| `left_edge_um_roi{roi_id}` | um | Left edge position converted to microns. |
| `right_edge_um_roi{roi_id}` | um | Right edge position converted to microns. |

## Diameter Values

| Column | Units | Description |
|---|---|---|
| `diameter_px_roi{roi_id}` | px | Raw diameter estimate in pixels. |
| `diameter_um_roi{roi_id}` | um | Raw diameter converted to microns. |
| `diameter_px_filt_roi{roi_id}` | px | Post-filtered diameter in pixels. |
| `diameter_was_filtered_roi{roi_id}` | bool (`0`/`1`) | Whether post-filter replaced the raw diameter at this timepoint. |

## Intensity Values

| Column | Units | Description |
|---|---|---|
| `sum_intensity_roi{roi_id}` | arbitrary intensity units | Sum of the per-timepoint processed profile intensity. |
| `peak_roi{roi_id}` | arbitrary intensity units | Peak intensity in the profile used for detection. |
| `baseline_roi{roi_id}` | arbitrary intensity units | Baseline intensity in the profile used for detection. |

## Edge Strength

| Column | Units | Description |
|---|---|---|
| `edge_strength_left_roi{roi_id}` | intensity/px | Left-edge gradient strength. |
| `edge_strength_right_roi{roi_id}` | intensity/px | Right-edge gradient strength. |

## Quality Control Fields

| Column | Units | Description |
|---|---|---|
| `qc_score_roi{roi_id}` | unitless (0-1) | Aggregate QC confidence score. |
| `qc_flags_roi{roi_id}` | string list (`|`-delimited) | QC flag names for this timepoint. |
| `qc_edge_violation_roi{roi_id}` | bool (`0`/`1`) | Motion/edge-shift QC violation flag. |
| `qc_diameter_violation_roi{roi_id}` | bool (`0`/`1`) | Diameter-change QC violation flag. |
| `qc_center_violation_roi{roi_id}` | bool (`0`/`1`) | Center-shift QC violation flag. |
