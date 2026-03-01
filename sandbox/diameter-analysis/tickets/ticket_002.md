# ticket_002.md — Implement stepping + binning + stride + threaded backend (chunked)

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
- parallel execution using threads with chunking, producing identical results to serial.

## Scope (STRICT)

### Allowed edits
- `kymflow/sandbox/diameter-analysis/**`

### Forbidden edits
- Anything outside `kymflow/sandbox/diameter-analysis/`

## Requirements
R1: Define dataclasses/enums (locations per your architecture snapshot):

- `DiameterDetectionParams` with `to_dict()` and `from_dict()` for JSON sidecar.
  Must include at least:
  - `roi_id` (or passed externally), `roi=(t0,t1,x0,x1)` (or separate fields),
  - `window_rows_odd` (int, odd >=1),
  - `stride` (int >=1),
  - `binning_method` (mean/median),
  - `polarity` (bright_on_dark | dark_on_bright),
  - `diameter_method` (at least threshold-width),
  - any threshold parameters (e.g., half-max, fixed, etc.) as needed.

- `BinningMethod` enum: `MEAN`, `MEDIAN`
- `Polarity` enum (or Literal) with `BRIGHT_ON_DARK`, `DARK_ON_BRIGHT`
- `DiameterMethod` enum: at least `THRESHOLD_WIDTH` (others may be placeholders)
- `DiameterResult` dataclass (one per emitted center index) including:
  - `center_row` (int), `time_s` (float),
  - `left_edge_px`, `right_edge_px`, `diameter_px` (floats; allow NaN),
  - `left_edge_um`, `right_edge_um`, `diameter_um` (either stored or computed helpers),
  - `peak`, `baseline` (float),
  - `qc_score` (float in [0,1]),
  - `qc_flags` (list[str] or bitmask).

R2: Implement stepping engine:

- Iterate center indices within ROI time bounds.
- For each center index, compute window rows (odd size) centered on `i`:
  - clamp to ROI time bounds at edges.
- Apply mean/median across selected rows → 1D profile over ROI space bounds.
- Apply polarity transform (if dark_on_bright, invert or equivalent).
- Implement `stride` so emitted indices are:
  - `i = roi_t0, roi_t0+stride, ... < roi_t1`
  - and each emitted result stores `center_row=i` and `time_s=i * seconds_per_line`.

R3: Implement threshold-width diameter (v1):

- Compute baseline + peak robustly (document method used).
- Determine threshold (default half-max; allow configurable later).
- Find left/right crossing indices; handle missing crossings gracefully:
  - do not crash,
  - set diameter/edges to NaN,
  - add QC flags indicating why.

R4: QC metrics (v1) must exist and be recorded per step:

At minimum:
- contrast metric (peak-baseline),
- saturation detection (near min/max or high percentile clamp),
- “double peak” heuristic,
- “missing edges”.

Compute a `qc_score` in [0,1] from simple weighted heuristics.
Document that this is provisional.

R5: Parallel backend (threads) with chunking:

- Add `backend="serial"|"threads"` param to `analyze()`.
- Thread backend must chunk indices (e.g., 256–2048 centers per task) to reduce overhead.
- Must produce identical results to serial for deterministic synthetic inputs.
- Ensure stable ordering of returned results by center_row.

R6: Saving/loading:

Implement `save_analysis()` writing two sidecars (each may span multiple ROIs by `roi_id`):
- `analysis_params.json`: mapping `roi_id -> DiameterDetectionParams.to_dict()`
- `analysis_results.csv`: one row per emitted result, with `roi_id` column.

Implement `load_analysis()` restoring both.

R7: Update plotting functions to accept `list[DiameterResult]` and:
- overlay left/right edges on the image,
- plot diameter vs time.

Plotting should support both matplotlib and plotly dict-first.

## Acceptance criteria
- `uv run pytest -q` passes and includes tests verifying:
  - stride semantics (center_row/time_s correctness),
  - serial vs threads equality on a synthetic kymograph,
  - save/load round-trip for params and CSV rows count.

- `uv run python run_example.py` runs and produces:
  - stacked (2×1) matplotlib view (image + diameter vs time),
  - plotly dict outputs for same two views (printing short summary is OK).

- No crashes on missing edges; QC flags are recorded instead.

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
