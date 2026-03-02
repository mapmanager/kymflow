# ticket_8.md — Thin runner + minimal stable summary schema + no CLI + API conveniences

## Context
Folder boundary (HARD):
kymflow/sandbox/heart_rate_analysis/heart_rate/

Current pain points:
- `run_heart_rate_examples_fixed2.py` is too “fat” (argparse, dict-get chains, dataframe slicing, passing methods).
- We need a **stable, minimal, JSON-serializable summary schema** suitable for batch (400+ files).
- We want to keep *internal* QC rich, but expose only a small set of QC fields in the *output summary*.

This ticket:
1) removes CLI/argparse from the runner and relies on dataclass defaults
2) adds explicit API helpers to avoid caller-side dict-get and df slicing
3) makes `run_roi()` run both methods by default (no `methods=...` at call sites)
4) introduces a compact “batch summary” schema and a clear “bad trace” status string

## Scope (STRICT)

### Allowed edits
- heart_rate_pipeline.py
- run_heart_rate_examples_fixed2.py
- tests/ (add/modify tests)
- docs/ (add/modify markdown docs)

### Forbidden edits
- heart_rate_analysis.py (do not modify)
- heart_rate_plots.py (do not modify)
- Any other file in the repo

## Requirements

### R1 — Remove/reduce CLI parsing in the runner (make it thin)
In `run_heart_rate_examples_fixed2.py`:
- Remove `argparse` and `parse_args()` entirely (or leave a tiny stub that is unused).
- Use dataclass defaults:
  - `cfg = HRPlotConfig()` and/or `analysis_cfg = HRAnalysisConfig()` (whichever exists today).
- Keep `DEFAULT_FILES` hard-coded and in control of the user.
- Keep `ROI_ID = 1` at the top and validate it exists in each CSV.

Runner should:
- load CSV
- run analysis via the API (no df slicing in the runner)
- print *minimal batch summary* (see R4)
- generate plots as before

### R2 — Add API helpers so caller doesn’t slice df or use dict.get chains
In `HeartRateAnalysis` (heart_rate_pipeline.py), add methods:

- `get_roi_df(self, roi_id: int) -> pd.DataFrame`
  - returns a copy or view filtered to roi_id
  - raises KeyError/ValueError if roi_id missing

- `get_time_velocity(self, roi_id: int) -> tuple[np.ndarray, np.ndarray]`
  - returns t, v arrays for that roi, sorted by time if needed
  - raises if empty

- `get_roi_results(self, roi_id: int) -> HeartRatePerRoiResults`
  - returns cached results for roi_id
  - raises if not analyzed yet

- `get_roi_summary(self, roi_id: int, *, minimal: bool = True) -> dict`
  - returns the per-roi portion of the summary, without requiring caller-side dict navigation
  - when minimal=True, returns the minimal schema described in R4

### R3 — `run_roi()` runs both methods by default (no caller method selection)
Update `HeartRateAnalysis.run_roi(...)` signature/behavior:
- Remove `methods` parameter OR make it optional and default to both.
- Default behavior MUST run:
  - Lomb–Scargle
  - Welch
- Ensure runner no longer passes methods.

(If you keep a `methods` parameter for advanced use, do not require it in the runner.)

Update docs accordingly.

### R4 — Minimal stable batch summary schema
We need a minimal output dict for batch runs with stable keys.

Add a method (or reuse `getSummaryDict`) that can produce:

- file-level meta:
  - `file` (basename or full path)
  - `roi_id`
  - `n_total`
  - `n_valid`
  - `valid_frac`
  - `t_min`, `t_max`

- per-method outputs (each optional if method fails):
  - `lomb_bpm`, `lomb_hz`, `lomb_snr`
  - `welch_bpm`, `welch_hz`, `welch_snr`

- minimal QC outputs (keep short):
  - `lomb_edge` (bool)
  - `welch_edge` (bool)
  - `lomb_bc` (band_concentration)  (float or None)
  - `welch_bc` (band_concentration) (float or None)

- agreement outputs:
  - `agree_delta_bpm` (abs(lomb_bpm - welch_bpm)) or None
  - `agree_ok` (bool or None)
    - agree_ok True if delta_bpm <= `agree_tol_bpm` (configurable, default 30 bpm)

- status outputs:
  - `status` (one of: "ok", "insufficient_valid", "no_peak_lomb", "no_peak_welch", "method_disagree", "other_error")
  - `status_note` (short human-readable reason; empty string if ok)

Implementation notes:
- Minimal summary should be JSON-serializable.
- Do NOT include raw segment series in minimal summary.

Add a config constant (in pipeline module) for:
- `AGREE_TOL_BPM_DEFAULT = 30.0`

### R5 — Docs
Add/update:
- `docs/batch_summary_schema.md`
  - explains each key, meaning, and interpretation
  - defines `bc` as band_concentration
  - defines agreement logic and tolerance

### R6 — Tests
Add tests that:
- runner no longer depends on argparse (basic import test / grep optional)
- `get_roi_df`, `get_time_velocity`, `get_roi_results`, `get_roi_summary` behave as specified
- minimal summary includes the expected keys
- status classification triggers on synthetic bad traces:
  - too few valid points -> status="insufficient_valid"
  - mismatch between methods -> status="method_disagree" (can simulate by stubbing results in test)

Run:
- `uv run pytest -q`

## Acceptance criteria
- Runner executes without CLI args and prints minimal summary for each file.
- No df slicing in runner; it uses HeartRateAnalysis APIs.
- No dict.get(...) chains for per-roi summaries in runner.
- `run_roi()` does not require methods selection.
- Tests pass.

## Codex implementation report
Save:
- tickets/ticket_8_codex_report.md
