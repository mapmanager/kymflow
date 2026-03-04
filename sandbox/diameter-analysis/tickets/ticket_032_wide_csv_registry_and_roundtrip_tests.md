# Ticket 032 — Wide CSV registry + drift-safe load + roundtrip tests

## Goal
Make the **wide CSV** export/import **schema-driven, drift-safe, and tested**, so multi-(roi,channel) analysis can be reliably persisted and reloaded.

This ticket is **serialization/robustness only** — no algorithm behavior changes.

## Background
After Tickets 027–031, the pipeline treats `(roi_id, channel_id, roi_bounds)` as **required** for analysis and persistence.

The wide CSV format is convenient for end users, but it is fragile unless we:
- Define a **single canonical field registry** for CSV-exported arrays/metrics
- Encode `(roi_id, channel_id)` into column names using **single-underscore separators**
  - `{field}_roi{roi_id}_ch{channel_id}`
- Ensure every CSV export includes a **time axis column** (or equivalent) so a row can be interpreted
- Add **roundtrip tests** to catch drift immediately

## Scope

### A) Create a canonical registry for wide CSV fields
1. In `diameter_analysis.py` (or a dedicated `csv_schema.py` if you prefer), define:
   - `WIDE_CSV_TIME_COLUMNS`: e.g. `time_s` (and optionally `frame_idx`)
   - `WIDE_CSV_ARRAY_FIELDS`: list of per-time fields exported per run (edges, center, diameter, etc)
   - `WIDE_CSV_SCALAR_FIELDS`: list of scalar metadata columns (if any)

2. All wide CSV writer/loader code must use these registries.

### B) Enforce required time columns
- Wide CSV export must **always** include `time_s` (or a similarly named canonical time column).
- Loader must fail fast if the time column is missing.

### C) Drift-safe loader
- Loader should not depend on “center_row” or other incidental ordering.
- It must parse columns by:
  1) identifying `(roi_id, channel_id)` runs from suffixes
  2) mapping registered fields to arrays

### D) Roundtrip tests
Add tests that cover:
1. **Single run** roundtrip:
   - Generate a small synthetic result bundle for `(roi_id=1, ch=1)`
   - Export to wide CSV rows
   - Reload
   - Assert all arrays equal (within float tolerance) and required ids preserved

2. **Multi-run** roundtrip:
   - Two ROIs and/or two channels, e.g. `(roi=1,ch=1)` and `(roi=2,ch=1)`
   - Ensure columns are disambiguated and both runs load back correctly

3. **Fail-fast cases**:
   - Missing `time_s` column → raises
   - Missing required field column for a run → raises

## Non-goals
- No GUI changes
- No changes to detection methods or thresholds

## Acceptance criteria
- Wide CSV always has `time_s` (and tests enforce it).
- Column naming uses `_roi{roi_id}_ch{channel_id}` (single underscores).
- Loader is registry-driven and fails fast on missing required pieces.
- Roundtrip tests pass for single and multi-(roi,channel) bundles.

## Notes for Codex
- **No backward compatibility** defaults.
- Do not add `row.get(..., default)` fallbacks for required fields.
- Prefer raising `KeyError` / `ValueError` with a clear message.
