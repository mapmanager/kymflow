# ticket_029_multi_roi_channel_csv_flat_columns.md

## Goal
Support saving/loading **multiple diameter analyses per kymimage** (multiple `(roi_id, channel_id)` runs) into a **single pair** of files:
- `*.json` sidecar (structured, canonical)
- `*.csv` (flat, wide, Excel-friendly)

This ticket is about **schema + serialization layout** (and minimal plumbing), **not** changing detection behavior.

## Hard rules (must follow)
1. **Fail-fast / no backward compatibility unless explicitly specified**
   - Do **NOT** add defaults like `row.get("channel_id", "1")` for required fields.
   - If a required key is missing → raise `ValueError` (or `KeyError`) immediately.
2. **Required means required**
   - `roi_id` and `channel_id` are **required everywhere** once analysis runs.
   - They must be **non-optional** in `DiameterResult` and any container schemas.
3. **Column naming uses single underscore `_` separators**
   - Use: `{field}_roi{roi_id}_ch{channel_id}`
   - Do **NOT** use double-underscore `__`.
4. **All code changes are inside `sandbox/diameter-analysis/` only.**
   - Do **NOT** modify anything under `kymflow/` outside the sandbox.

## Background / current state (post ticket_028)
- `DiameterAnalyzer.analyze(...)` requires explicit `roi_id`, `roi_bounds`, `channel_id`.
- Each produced `DiameterResult` carries `roi_id` and `channel_id` (and should be strict).

## Deliverables
### 1) Introduce a multi-run results container (serialization-ready)
Add a new dataclass (location: `diameter_analysis.py` or a nearby module already used for serialization):

Example:
```python
@dataclass(frozen=True)
class DiameterRunKey:
    roi_id: int
    channel_id: int

@dataclass
class DiameterAnalysisBundle:
    # keyed runs, each run is a list[DiameterResult] aligned to frames/time within its ROI crop
    runs: dict[tuple[int, int], list[DiameterResult]]  # (roi_id, channel_id) -> results
    schema_version: int = 1
```

Notes:
- Keep key as `tuple[int,int]` to stay simple and JSON-friendly.
- This ticket does **not** require changing core `DiameterAnalyzer` internals yet; it can build this bundle from multiple calls.

### 2) JSON sidecar schema for multiple runs
Implement:
- `DiameterAnalysisBundle.to_dict()` / `from_dict()` (fail-fast for missing keys)
- JSON layout suggestion (canonical):
```json
{
  "schema_version": 1,
  "runs": {
    "roi1_ch1": { "roi_id": 1, "channel_id": 1, "results": [ ... rows ... ] },
    "roi2_ch1": { "roi_id": 2, "channel_id": 1, "results": [ ... ] }
  }
}
```
Or use string key `"1:1"`; pick one and document it in docstring.
**Do not** silently accept missing `roi_id/channel_id`.

### 3) CSV “flat wide” format (Excel-friendly)
Implement:
- `bundle_to_wide_csv_rows(bundle, *, include_time=True, include_qc=True) -> (header: list[str], rows: list[list[str]])`
- `bundle_from_wide_csv_rows(header, rows) -> DiameterAnalysisBundle`

**Column naming**
- Always include a base time column: `time_s` (global index for row alignment).
- For each run `(roi_id, channel_id)` and each per-frame metric, create a column:
  - `diameter_um_roi1_ch1`
  - `left_um_roi1_ch1`
  - `right_um_roi1_ch1`
  - `center_um_roi1_ch1`
  - `qc_flags_roi1_ch1`
  - etc.

Use the `_roi{roi}_ch{ch}` suffix convention consistently.

**Alignment**
- Wide CSV rows are aligned on `time_s` index.
- If runs have different lengths (due to different ROI bounds), shorter runs should write empty/NaN cells for out-of-range rows.
- Do **not** invent defaults for roi/channel; runs are explicit.

### 4) Strict construction checks inside analysis
Add an assertion (or explicit runtime check) that **every** `DiameterResult` built inside `analyze()` carries:
- exactly the `roi_id` passed to `analyze()`
- exactly the `channel_id` passed to `analyze()`

No mutation later, no optional.

### 5) Tests
Add/extend pytest tests:
1. **No-defaults test**: removing `channel_id` or `roi_id` from a row/dict causes failure.
2. **Round-trip JSON**: bundle → dict/json → bundle equals (for at least 2 runs).
3. **Round-trip CSV wide**: bundle → wide csv → bundle equals (or equivalent with float tolerance).
4. **Column naming** uses `_` and matches `{field}_roi{roi}_ch{ch}`.
5. **Strict analyze propagation**: create synthetic run and verify every result has passed roi/channel.

### 6) Docs
Update/add a short section in `docs/` describing:
- bundle JSON schema
- wide CSV schema + naming convention
- explicit statement: “No backward compatibility defaults; missing keys are errors.”

## Acceptance checks
- `uv run pytest` passes.
- Exported CSV uses `_roi{roi}_ch{ch}` (single underscore separators).
- Missing `roi_id` or `channel_id` in any row/dict raises immediately.
- At least one test covers multi-run bundle (two different roi_ids or channel_ids).

