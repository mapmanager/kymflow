# Multi-Run Serialization

## Sidecar JSON schema (metadata-only, v2)
Diameter sidecar JSON is metadata-only and does not duplicate per-row result arrays.

- Top-level keys:
  - `schema_version` (required, must be `2`)
  - `source_path` (required string path)
  - `rois` (required object)
- ROI key format: `"<roi_id>"` (string int)
- Each ROI object requires:
  - `channel_id`
  - `roi_bounds_px` (`[t0, t1, x0, x1]`)
  - `detection_params`

Example:

```json
{
  "schema_version": 1,
  "runs": {
    "1": {
      "channel_id": 1,
      "roi_bounds_px": [0, 100, 0, 64],
      "detection_params": {"stride": 1}
    },
    "2": {
      "channel_id": 3,
      "roi_bounds_px": [10, 80, 2, 60],
      "detection_params": {"stride": 2}
    }
  }
}
```

## Wide CSV schema
Wide CSV is aligned on a base `time_s` column and per-run metric columns.

Wide CSV export/import is registry-driven in `diameter_analysis.py`:

- `WIDE_CSV_TIME_COLUMNS`
- `WIDE_CSV_ARRAY_FIELDS`
- `WIDE_CSV_SCALAR_FIELDS`

Column naming convention:

- `{field}_roi{roi_id}`
- Single underscore separators only.
- Example columns:
  - `diameter_px_roi1`
  - `left_edge_px_roi2`
  - `qc_flags_roi2`

Shorter runs leave empty cells for out-of-range rows.
Wide CSV load is aligned by `time_s` and registered run fields; it does not depend on `center_row` ordering.
Wide CSV parsing behavior:

- Columns that match wide pattern `{field}_roi{roi_id}_ch{channel_id}` must use registered fields; unknown wide columns are rejected.
- Unrelated non-wide columns are ignored.

## Fail-fast contract
No backward-compatibility defaults are applied for required IDs.

- Missing required keys (`roi_id`, `channel_id`) in row/dict payloads are errors.
- Invalid run key names are errors.
- Required means required across analysis, bundle JSON, and wide CSV parsing.
