
# Ticket 041 — Refactor diameter analysis serialization (JSON metadata-only, CSV source of truth)

## Background

The current serialization format stores analysis results in two places:

- JSON sidecar (`.diameter.json`)
- CSV results file (`.diameter.csv`)

JSON currently stores per-row analysis results (`runs[*].results`) which duplicate the data already written to CSV.
This duplication increases complexity, file size, and maintenance cost.

This ticket refactors the format so that:

- CSV is the **single source of truth for analysis results**
- JSON stores **only metadata describing what was analyzed and how**

Old JSON result duplication will be removed entirely.

This change is **breaking**, so the schema version must be bumped.

---

# High-Level Design

## JSON becomes metadata-only

Remove all per-row analysis data from JSON.

JSON will only record **what was analyzed and how**.

### New JSON structure

{
  "schema_version": 2,
  "source_path": "...",
  "rois": {
    "1": {
      "channel_id": 1,
      "roi_bounds_px": [t0, t1, x0, x1],
      "detection_params": {...}
    },
    "2": {
      "channel_id": 1,
      "roi_bounds_px": [t0, t1, x0, x1],
      "detection_params": {...}
    }
  }
}

### Meaning

- `schema_version`
  - Version of serialization format.
  - Must be **2** for this new format.

- `source_path`
  - Path to analyzed TIFF.

- `rois`
  - Dictionary keyed by ROI id (string).

Each ROI entry records:

- `channel_id`
- `roi_bounds_px = [t0, t1, x0, x1]`
- `detection_params`

`roi_bounds_px` uses **pixel indices in kymograph coordinates**:

(t0, t1, x0, x1) = (time_start, time_end, space_start, space_end)

Ranges are **half-open pixel indices**.

---

# CSV becomes the only result store

CSV contains **all time-series analysis results**.

Example columns:

time_s  
left_edge_px_roi1  
right_edge_px_roi1  
diameter_px_roi1  
left_edge_um_roi1  
right_edge_um_roi1  
diameter_um_roi1  
sum_intensity_roi1  
qc_score_roi1  
qc_flags_roi1  

Column names **drop `_ch{channel}`**.

Old:

diameter_px_roi1_ch1

New:

diameter_px_roi1

Channel identity is now stored **only in JSON metadata**.

Constraint:

Each ROI may be analyzed on **exactly one channel per saved analysis bundle**.

---

# Global time axis rule

CSV must always contain a global time axis:

time_s

Rules:

- `time_s` must exist.
- It represents the full time axis of the TIFF.
- All ROI columns must have the same row count as `time_s`.

ROI results align to this axis.

For rows outside `(t0, t1)` of a given ROI:

values may be `NaN`.

---

# Loader behavior

Load order:

1. Load JSON metadata
2. Load CSV results

## Schema version

Loader must enforce:

schema_version == 2

If not:

Raise an error.

Backward compatibility with previous schema versions is **not required**.

---

# CSV validation per ROI

For each ROI declared in JSON:

Example:

roi_id = 1  
channel_id = 1

Expected CSV columns include:

left_edge_px_roi1  
right_edge_px_roi1  
diameter_px_roi1  

These required column names should be determined via the existing CSV registry logic, updated to remove `_ch`.

### Missing columns

If required columns are missing:

- Skip that ROI
- Emit `logger.error(...)`
- Emit `ui.notify(...)`

Other ROIs should still load normally.

---

# Remove JSON results entirely

Delete all code that reads or writes:

runs[*].results

Remove:

- JSON result serialization
- JSON → DiameterResult parsing
- JSON vs CSV parity checks

CSV becomes the only source of result data.

---

# Save behavior

Saving analysis must:

1. Write CSV results
2. Write JSON metadata

JSON must contain:

schema_version  
source_path  
rois

Each ROI entry must include:

channel_id  
roi_bounds_px  
detection_params

---

# Runtime behavior

Each ROI may be analyzed on exactly **one channel at a time**.

If user analyzes ROI 1 on a different channel later:

- JSON entry for ROI 1 updates to the new channel
- CSV columns `*_roi1` are overwritten on save

JSON is authoritative for:

roi_id → channel_id

---

# Non-goals

This refactor intentionally does NOT add:

- JSON result duplication
- JSON row count checks
- JSON time parity checks
- multi-channel per ROI support

---

# Implementation Steps

1. Bump schema_version to 2
2. Update JSON schema (`runs` → `rois`)
3. Remove JSON results serialization
4. Remove JSON results loading
5. Update CSV column naming (remove `_ch`)
6. Update column registry logic
7. Update loader validation logic
8. Update save logic
9. Update tests
10. Add tests for ROI skip behavior

---

# Acceptance Criteria

- JSON no longer contains per-row results
- CSV columns do not include `_ch`
- Loader reads ROI metadata from JSON
- Loader validates CSV columns per ROI
- Missing ROI columns cause skip + error
- schema_version == 2 enforced
- Tests updated and passing
