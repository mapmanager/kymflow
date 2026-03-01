# ticket_002.md — Implement stepping + binning + stride + threaded backend (chunked) [HARDENED]

## Mode
Exploration

## Context
Implement the real stepping engine for kymograph diameter analysis:

- symmetric odd row-window per center index,
- mean/median binning across window rows to produce a 1D spatial profile,
- stride support (emit every stride center index),
- ROI cropping `(t0,t1,x0,x1)` tuple (time start/stop, space start/stop),
- first diameter method implementation (threshold-width v1),
- QC metrics + flags scaffolding,
- parallel execution using threads with chunking, producing identical results to serial,
- persistence schema hardening (versioning) and avoiding duplicate/legacy implementations.

## Scope (STRICT)

### Allowed edits
- `kymflow/sandbox/diameter-analysis/**`

### Forbidden edits
- Anything outside `kymflow/sandbox/diameter-analysis/`

## Requirements

### R0: Refactor legacy placeholder analysis (NO DUPLICATES)
The ticket_001 scaffold may contain a placeholder threshold-width estimator. In this ticket:
- Move/replace any placeholder diameter logic so there is a SINGLE source of truth:
  the new stepping/binning engine in this ticket.
- Remove or clearly deprecate old/duplicate code paths so `DiameterAnalyzer.analyze(...)`
  uses the new engine for both serial and threads backends.

### R1: Define dataclasses/enums (locations per your architecture snapshot)

- `DiameterDetectionParams` with `to_dict()` and `from_dict()` for JSON sidecar.
  Must include at least:
  - `roi` as `(t0,t1,x0,x1)` (ints; half-open ranges OK; document convention),
  - `window_rows_odd` (int, odd >=1),
  - `stride` (int >=1),
  - `binning_method` (mean/median),
  - `polarity` (bright_on_dark | dark_on_bright),
  - `diameter_method` (at least threshold-width),
  - threshold parameter(s) for v1 (e.g., `threshold_mode="half_max"` and/or `threshold_value`).

- `BinningMethod` enum: `MEAN`, `MEDIAN`
- `Polarity` enum (or Literal) with `BRIGHT_ON_DARK`, `DARK_ON_BRIGHT`
- `DiameterMethod` enum: at least `THRESHOLD_WIDTH` (others may be placeholders)
- `DiameterResult` dataclass (one per emitted center index) including:
  - `center_row` (int), `time_s` (float),
  - `left_edge_px`, `right_edge_px`, `diameter_px` (floats; allow NaN),
  - `peak`, `baseline` (float),
  - QC: `qc_score` (float in [0,1]), `qc_flags` (list[str] or bitmask),
  - Optional: um values as stored fields OR helper properties using `um_per_pixel`.

### R2: Implement stepping engine (serial)
Implement a deterministic, serial stepping engine:

- Iterate emitted center indices within ROI time bounds:
  - `i = roi_t0, roi_t0 + stride, ... < roi_t1`
- For each center index `i`, compute window rows (odd size) centered on `i`:
  - Clamp to ROI time bounds at edges.
- Apply mean/median across selected rows → 1D profile over ROI space bounds.
- Apply polarity transform (if dark_on_bright, invert or equivalent).
- Compute and store `center_row=i` and `time_s=i * seconds_per_line`.
- Ensure results are returned in ascending `center_row` order.

### R3: Implement threshold-width diameter (v1)
Implement threshold-width diameter on the binned 1D profile:

- Compute baseline + peak robustly (document method used).
- Determine threshold (default half-max; allow configurable later).
- Find left/right crossing indices.
- Handle missing crossings gracefully:
  - do not crash,
  - set edges/diameter to NaN,
  - add QC flags indicating why (e.g., `missing_left_edge`, `missing_right_edge`).

### R4: QC metrics (v1) must exist per step
At minimum compute and record:
- contrast metric (peak-baseline),
- saturation detection (near min/max or high percentile clamp),
- “double peak” heuristic,
- “missing edges”.

Compute a `qc_score` in [0,1] from simple weighted heuristics.
Document that this is provisional.

### R5: Parallel backend (threads) with chunking
Add thread backend:

- Add `backend="serial"|"threads"` to `DiameterAnalyzer.analyze(...)`.
- Thread backend must chunk indices (e.g., 256–2048 centers per task) to reduce overhead.
- Chunk size should be configurable internally (constant or param), but MUST exist as a named variable.
- Must produce identical results to serial for deterministic synthetic inputs.
- Ensure stable ordering of returned results by `center_row` (sort/merge deterministically).

### R6: Persistence schema hardening (JSON + CSV)
Implement `save_analysis()`/`load_analysis()` with two sidecars (each may span multiple ROIs by `roi_id`):

1) `analysis_params.json` must include schema versioning:
   - Top-level key: `"schema_version": 1`
   - Top-level key: `"rois": { "<roi_id>": <params_dict>, ... }`

2) `analysis_results.csv`:
   - one row per emitted result,
   - must include `roi_id` column,
   - must include `schema_version` column OR the loader must accept a file-level version in the JSON and validate compatibility.

Round-trip must be tested.

### R7: Synthetic generator must expose ground truth (for tests)
Update synthetic generator so it can optionally return a ground truth diameter per emitted center index, sufficient to validate basic correctness.

Minimum requirements:
- Return `truth` with at least `truth_diameter_px` as a 1D array aligned to time rows (or emitted centers if you implement stride in the synthetic payload).
- Keep it deterministic with a seed.

### R8: Plotting updates
Update plotting functions to accept `list[DiameterResult]` and:
- overlay left/right edges on the image,
- plot diameter vs time.

Plotting should support both matplotlib and plotly dict-first.
For plotly, keep dict available (return dict). Using a Figure internally is OK.

## Acceptance criteria
- `uv run pytest -q` passes and includes tests verifying:
  - stride semantics (center_row/time_s correctness),
  - serial vs threads equality on a deterministic synthetic kymograph,
  - save/load round-trip for params JSON (schema_version + rois mapping) and CSV rows count,
  - synthetic ground truth exists and the threshold-width estimate is within a parameterized tolerance.

- `uv run python run_example.py` runs and produces:
  - stacked (2×1) matplotlib view (image + diameter vs time),
  - plotly dict outputs for same two views (printing short summary is OK).

- No crashes on missing edges; QC flags are recorded instead.
- No duplicate/legacy analysis path remains: analyze() uses the new engine.
- No edits outside allowed scope.

## Validation commands
- `uv run pytest -q`
- `uv run python run_example.py`

## Notes / constraints
- Thread backend is the first parallel step; a process backend may be added later.
- Keep chunking logic internal; do not overcomplicate the public API.
- If you introduce multiprocessing in future tickets, macOS requires an `if __name__ == "__main__":` guard.

## Codex implementation report
Save:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_002_codex_report.md`
