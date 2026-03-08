# Ticket 046 — Finalize metadata-only JSON + CSV-only results as single source of truth (hard fail-fast)

## Context / Problem
We have spent multiple tickets trying to reach a stable, *single* save/load contract:
- **CSV is the only source of truth for per-timepoint results.**
- **JSON is metadata-only** (what was analyzed + how): schema_version, source_path, per-ROI channel_id, ROI bounds, detection_params.
- No legacy/dual parsing paths.
- No backward-compat defaults for required fields.

Recent Codex iterations have left the system in an unstable state (regressions, drift, and inconsistent behavior). This ticket is an aggressive cleanup to **end the churn** by enforcing one contract and deleting anything else.

## Scope (do only this)
1) **Enforce ONE JSON schema (metadata-only)**
2) **Enforce ONE CSV schema (wide columns, results only)**
3) **Loader behavior**: “skip ROI with loud error” when CSV missing required ROI columns declared by JSON.
4) **Remove remaining fallback/compat code** related to ROI/channel required fields.
5) **Tests**: add a minimal but strict set of tests that lock the contract.

## Non-goals
- No GUI UX changes beyond what is required to keep the app working with the unified contract.
- No algorithm changes (edge detection, QC, filtering, etc).

---

## Current desired on-disk formats

### JSON (metadata-only)
- File: `<tif>.diameter.json`
- Must contain (example):
```json
{
  "schema_version": 1,
  "source_path": ".../cell10_C001T001.tif",
  "rois": {
    "1": {
      "roi_id": 1,
      "roi_bounds_px": [0, 9999, 0, 127],
      "channel_id": 1,
      "detection_params": { "...": "DiameterDetectionParams.to_dict()" }
    }
  }
}
```

Rules:
- `schema_version` is required and must equal the **single supported value**.
- `rois` keys are ROI ids as strings. Each ROI entry must include:
  - `roi_id` (int)
  - `roi_bounds_px` (length-4 list[int] as (t0,t1,x0,x1))
  - `channel_id` (int)
  - `detection_params` (dict)

### CSV (results only; wide)
- File: `<tif>.diameter.csv`
- Must contain:
  - `time_s` column (global time axis; full length of kym time dimension)
  - For each ROI declared in JSON: required columns with suffix `_roi{roi_id}` **(NO `_ch` suffix)**.
    - Example required minimum set:
      - `left_edge_px_roi1`
      - `right_edge_px_roi1`
      - `diameter_px_roi1`
      - plus whatever else the registry declares as required for reconstruction.

Rules:
- CSV may contain extra unrelated columns: allowed.
- CSV may contain ROI columns for ROIs not in JSON: allowed/ignored.
- CSV missing required columns for ROI declared in JSON => **skip that ROI**, emit:
  - `logger.error(...)` mentioning ROI id and missing columns
  - optional UI notify (if loader is in GUI path)
- If **all** ROIs declared in JSON fail to load => raise (fail fast).

---

## Implementation tasks

### A) Delete/Disable any remaining legacy/dual-path code
- There must be exactly one pair of public functions in the backend:
  - `save_analysis_sidecars(...)` (or current equivalent)
  - `load_analysis_sidecars(...)`
- Remove any old functions that:
  - serialize per-row results into JSON
  - try to parse “old” JSON formats
  - do “just in case” branching based on presence of JSON keys that belong to legacy formats

### B) Hard fail-fast for required fields
- No `row.get("channel_id", "1")` or similar defaults anywhere in save/load.
- No Optional typing for required IDs in runtime objects if they are logically required.
- JSON loader:
  - validate required keys exist and types are correct
  - if missing required keys: raise `ValueError` (do not guess or default)

### C) Explicit ROI skip behavior (JSON->CSV crosscheck)
- Use JSON `rois` entries to compute expected ROI suffixes and required columns.
- For each ROI declared in JSON:
  - if CSV has all required columns => load ROI results into runtime
  - else => skip ROI (log error)
- After loop:
  - if no ROI loaded => raise

### D) Tests (must add)
Add/adjust tests (prefer adding new ones in `tests/`):
1. **test_json_schema_version_fail_fast**
   - schema_version missing or wrong => raise
2. **test_skip_roi_missing_columns**
   - JSON declares ROI1 and ROI2
   - CSV missing ROI1 required columns but has ROI2 => ROI2 loads, ROI1 skipped
3. **test_csv_extra_columns_tolerated**
   - Add unrelated extra columns => load still succeeds
4. **test_roi_columns_not_in_json_ignored**
   - CSV contains roi999 columns not declared in JSON => ignored
5. **test_no_legacy_json_results**
   - Ensure saved JSON does not contain per-row `results` lists anywhere

---

## Acceptance criteria
- App path works:
  - Detect → Save → Restart → Select file → Load overlays + line plot from sidecars
- JSON on disk contains **no per-row results**.
- CSV is the only per-row results source.
- Loader implements **skip ROI with loud error** and fails only if none load.
- Tests above pass and protect against regression.

---

## Files likely touched
- `diameter_analysis.py`
- `serialization.py` (if used for sidecars)
- tests: `tests/test_multi_run_serialization.py` and/or new tests

## Notes to Codex (important)
- Do **not** introduce backward compatibility parsing.
- Do **not** add default values for missing required fields.
- Prefer deleting dead/legacy code over keeping “legacy” branches.
