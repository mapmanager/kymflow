# Multi-Run Serialization

## Contract Summary
- JSON (`.diameter.json`) is metadata only.
- CSV (`.diameter.csv`) is the authoritative source for per-timepoint numeric results.

## JSON Sidecar Schema
Required top-level keys:
- `schema_version` (required exact match to the single supported version)
- `source_path` (required string)
- `rois` (required object)

ROI map:
- Key format: `"<roi_id>"` (string integer)
- Each ROI object must include:
  - `roi_id` (int, must match key)
  - `roi_bounds_px` (`[t0, t1, x0, x1]`, required list of 4 ints)
  - `channel_id` (required int)
  - `detection_params` (required dict)

JSON does not contain per-row results arrays.

Example:

```json
{
  "schema_version": 2,
  "source_path": "/path/to/cell10_C001T001.tif",
  "rois": {
    "1": {
      "roi_id": 1,
      "roi_bounds_px": [0, 100, 0, 64],
      "channel_id": 1,
      "detection_params": {
        "stride": 1,
        "window_rows_odd": 5
      }
    },
    "2": {
      "roi_id": 2,
      "roi_bounds_px": [10, 80, 2, 60],
      "channel_id": 3,
      "detection_params": {
        "stride": 2,
        "window_rows_odd": 5
      }
    }
  }
}
```

## CSV Wide Schema
CSV includes:
- global `time_s` column
- per-ROI columns with suffix `_roi{roi_id}`

Example columns:
- `diameter_px_roi1`
- `left_edge_px_roi2`
- `qc_flags_roi2`

CSV parsing policy:
- Required reconstruction columns are registry-driven (`WIDE_CSV_REGISTRY.required_recon_fields`).
- For each ROI declared in JSON:
  - missing required ROI columns -> ROI is skipped and `logger.error(...)` is emitted.
- If all JSON-declared ROIs fail column validation -> load fails.
- Extra unrelated CSV columns are tolerated.
- Extra ROI columns not declared in JSON are ignored (warning).

## Fail-Fast Rules
- No backward-compat defaults for required metadata fields.
- Missing required JSON keys raise immediately.
- Unsupported `schema_version` raises immediately.
- Legacy JSON keys (such as `runs`/`results`) are rejected.
