# Ticket 044 — Metadata-only JSON + Wide CSV as sole source of truth (remove legacy bundle JSON results)

## Goal
Finish the serialization refactor by making **CSV the only results source of truth** and making JSON **metadata-only**, with **no legacy/alternate save/load paths** remaining.

This ticket fixes the remaining critical issues identified after Ticket 043:
1) legacy bundle JSON-results save/load still exists,
2) dual schema/version drift risk remains,
3) load behavior is hard-fail vs “skip ROI with loud error”,
4) tests still lock in the legacy bundle pathway.

## Non-goals
- No algorithm changes.
- No GUI redesign beyond updating call sites to the new API (if needed).
- No backward compatibility / defaults / silent fallbacks.

## Source of truth
Use the current repository state. Do not introduce second/legacy formats.

---

## Requirements

### R1 — Remove legacy JSON-results path completely
**Delete (or fully deprecate by removal from codebase) any API that writes/reads per-row results into JSON.**
- Remove `save_diameter_analysis(...)` / `load_diameter_analysis(...)` if they serialize `runs[*].results` into JSON.
- Remove/stop using `DiameterAnalysisBundle.to_dict()/from_dict()` if they imply JSON contains results.
- Ensure no imports/call sites (GUI or tests) use the removed APIs.

**Acceptance**
- Grep: there is no code path that writes JSON with `runs[*].results` (or equivalent per-row list).
- Only the metadata-only JSON file is produced/consumed.

### R2 — Enforce single JSON schema (metadata-only) with fail-fast version check
Define ONE JSON schema (metadata-only) and enforce it strictly:
- `schema_version` required and must match exactly (fail fast).
- JSON must contain:
  - `schema_version`
  - `source_path` (string)
  - `rois` mapping of roi_id (string keys) → object containing:
    - `roi_id` (int) OR infer from key but store consistently (pick one; no silent coercion)
    - `roi_bounds_px` as (t0,t1,x0,x1) ints (required)
    - `channel_id` (int, required)
    - `detection_params` dict (required; produced by `DiameterDetectionParams.to_dict()`)
- JSON must NOT contain per-row results.

**Acceptance**
- Loading JSON with missing required fields raises immediately.
- Loading JSON with wrong schema_version raises immediately.

### R3 — Loader policy: tolerant extras, strict diameter schema; skip ROI with loud error
When loading analysis:
- JSON declares which ROIs exist and their metadata.
- CSV is loaded once (wide format).
- For each ROI declared in JSON:
  - Validate required columns exist for that ROI (based on registry).
  - If required columns are missing/invalid for a ROI:
    - **skip only that ROI**
    - emit **logger.error** (and if in GUI, surface ui.notify warning)
  - Continue loading other ROIs.

Policy for “extra” CSV columns:
- Allow unrelated columns freely.
- For columns that *look like* registry columns (match the pattern for ROI-wide fields), enforce they either:
  - correspond to a ROI declared in JSON, or
  - are ignored (but do not hard-fail the whole load). Prefer: ignore + logger.warning.

**Acceptance**
- Test: JSON declares ROI1+ROI2; CSV missing ROI1 required columns → ROI2 loads, ROI1 skipped, error emitted.
- Test: CSV contains extra ROI columns not present in JSON → ignored (or warning), load still succeeds for JSON-declared ROIs.

### R4 — Tests updated to match the new contract (no legacy bundle roundtrip)
Update tests so they enforce ONLY:
- metadata-only JSON format
- wide CSV as results source of truth
- registry-driven column contract

Remove tests that assert JSON-results bundle roundtrip.

**Acceptance**
- `test_multi_run_serialization.py` (and any others) no longer depend on bundle JSON containing per-row results.
- New/updated tests cover R2 and R3.

---

## Implementation notes (guidance, not optional)
- Do **not** add “backward compatibility” defaults like `row.get(..., "1")` for required fields.
- Do **not** keep legacy code behind flags; remove it.
- Prefer explicit, small helper functions:
  - `save_analysis_metadata_json(...)`
  - `load_analysis_metadata_json(...)`
  - `load_analysis_from_csv_with_metadata(...)`

---

## Files likely touched
- `diameter_analysis.py` (remove legacy, enforce schema, implement skip-ROI loader behavior)
- `tests/test_multi_run_serialization.py` (remove legacy assertions; add R2/R3 tests)
- Any GUI controller call sites that still invoke legacy save/load APIs

---

## Definition of Done
- Only one save/load system exists.
- JSON is metadata-only; CSV is results-only.
- Version/schema enforcement is strict.
- Load behavior skips bad ROIs and loads good ones.
- Tests enforce the new contract and no legacy behavior remains.
