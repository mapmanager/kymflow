
# Ticket 043 — Enforce JSON schema + ROI column validation (strict, fail-fast)

## Goal

Finalize the serialization refactor by enforcing the **single supported schema** and
implementing **explicit CSV validation against JSON metadata**.

This ticket intentionally merges the planned Ticket 043 and 044 into one change so the
system reaches the final intended design in a single step.

After this ticket:

- JSON = metadata only
- CSV = numeric data source of truth
- Loader strictly validates schema
- Loader validates ROI columns in CSV
- Missing ROI data results in **ROI skipped + loud error**
- No backward compatibility

Fail fast when schema is invalid.

---

# Step 1 — Strict JSON schema validation

File:
serialization.py (or wherever JSON load occurs)

Immediately validate JSON structure after load.

Required structure:

{
  "schema_version": 2,
  "source_path": "...",
  "rois": {
      "1": {
          "channel_id": int,
          "roi_bounds": [t0,t1,x0,x1],
          "detection_params": {...}
      }
  }
}

Required checks:

1. schema_version must exist and equal expected value
2. rois must exist and be a dict
3. each roi entry must contain:
   - channel_id
   - roi_bounds
   - detection_params

Forbidden keys:

- runs
- results

If forbidden keys appear → raise ValueError.

Example:

    if "runs" in json_data or "results" in json_data:
        raise ValueError("Legacy JSON schema detected")

---

# Step 2 — CSV column validation against JSON ROIs

After JSON loads, verify CSV columns match expected ROI metadata.

Expected column pattern:

    *_roi{roi_id}

Example:

    left_edge_px_roi1
    diameter_px_roi1

Validation logic:

For each ROI in json["rois"]:

1. Determine required column prefix:

    roi_prefix = f"_roi{roi_id}"

2. Scan CSV header for columns containing that suffix.

3. If no columns exist for that ROI:

    - skip ROI
    - logger.error("Missing CSV columns for ROI %s", roi_id)
    - continue loading remaining ROIs

The loader must **not crash the entire load** for a single ROI failure.

---

# Step 3 — CSV extras policy

Columns present in CSV but not declared in JSON:

Allowed.

Ignore them.

This allows users to extend CSV externally without breaking load.

---

# Step 4 — Update tests

Add tests covering:

1. JSON schema enforcement

   - JSON containing "runs" must fail

2. Missing CSV columns for ROI

   JSON declares ROI1 and ROI2
   CSV only contains ROI2 columns

   Expected behavior:

       ROI1 skipped
       ROI2 loaded
       error logged

3. CSV extra ROI columns not declared in JSON

   Loader should ignore them and continue.

---

# Acceptance Criteria

1. Loader rejects legacy JSON structures.
2. Loader skips ROIs with missing CSV columns.
3. Loader logs explicit errors when skipping ROIs.
4. Loader tolerates extra CSV columns.
5. All tests pass.

---

# Non‑Goals

Do not:

- support legacy JSON
- add compatibility guards
- reintroduce JSON numeric results
