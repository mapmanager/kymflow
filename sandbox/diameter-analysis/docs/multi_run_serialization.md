# Multi-Run Serialization

## Bundle JSON schema
`DiameterAnalysisBundle` stores multiple analysis runs keyed by `(roi_id, channel_id)`.

- Top-level keys:
  - `schema_version` (required)
  - `runs` (required object)
- Run key format: `roi{roi_id}_ch{channel_id}`
- Each run object requires:
  - `roi_id`
  - `channel_id`
  - `results` (list of `DiameterResult` dict payloads)

Example:

```json
{
  "schema_version": 1,
  "runs": {
    "roi1_ch1": {
      "roi_id": 1,
      "channel_id": 1,
      "results": [
        {"roi_id": 1, "channel_id": 1, "center_row": 0, "time_s": 0.0}
      ]
    },
    "roi2_ch3": {
      "roi_id": 2,
      "channel_id": 3,
      "results": []
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

- `{field}_roi{roi_id}_ch{channel_id}`
- Single underscore separators only.
- Example columns:
  - `diameter_px_roi1_ch1`
  - `left_edge_px_roi2_ch3`
  - `qc_flags_roi2_ch3`

Shorter runs leave empty cells for out-of-range rows.
Wide CSV load is aligned by `time_s` and registered run fields; it does not depend on `center_row` ordering.

## Fail-fast contract
No backward-compatibility defaults are applied for required IDs.

- Missing required keys (`roi_id`, `channel_id`) in row/dict payloads are errors.
- Invalid run key names are errors.
- Required means required across analysis, bundle JSON, and wide CSV parsing.
