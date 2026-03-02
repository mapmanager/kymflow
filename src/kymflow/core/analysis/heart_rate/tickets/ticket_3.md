# ticket_3.md — Add OO pipeline: HeartRateAnalysis + per-ROI params/results + summary dict

## Context
Folder boundary (HARD):
kymflow/sandbox/heart_rate_analysis/heart_rate/

We want an object-oriented pipeline that:
- loads and retains the **entire CSV** (including multiple `roi_id` values)
- allows running HR analysis for **one specific roi_id at a time**
- stores **results per roi_id** internally
- stores a **unique set of detection parameters (config) per roi_id**
- can return:
  - per-roi summary (Welch + Lomb, with QC)
  - aggregate summary across all roi_id values analyzed so far

This OO layer must be built on top of existing atomic “free” functions in `heart_rate_analysis.py`
(where practical), to keep logic centralized and reusable.

## Scope (STRICT)

### Allowed edits
- heart_rate_pipeline.py   (NEW FILE)
- heart_rate_analysis.py
- run_heart_rate_examples_fixed2.py
- tests/test_heart_rate_pipeline.py   (NEW FILE)

### Forbidden edits
- heart_rate_plots.py  (do not modify in this ticket)
- Any other file in the repo

## Requirements

### R1 — Enforce presence of `roi_id` in CSV
The CSV loader MUST require a `roi_id` column. If `roi_id` column is missing, raise a clear error.

Rationale: mixed-ROI CSVs are expected; running analysis without explicit ROI identity is unsafe.

### R2 — Create `heart_rate_pipeline.py`
Add a new module `heart_rate_pipeline.py` containing:

1) `HeartRateResults` dataclass
   - Stores primary outputs + QC for one method.
   - Must support `.to_dict()` producing JSON-serializable values.

2) `HeartRatePerRoiResults` dataclass (or equivalent)
   - Holds results for one roi_id:
     - `lomb: Optional[HeartRateResults]`
     - `welch: Optional[HeartRateResults]`
     - `agreement: Optional[dict]` (Δbpm, ΔHz, etc) if both exist
     - metadata/QC: n_total, n_valid, valid_fraction, time_range, etc
   - Must support `.to_dict()`.

3) `HeartRateAnalysis` class
   - Responsible for loading/storing the entire CSV and caching per-roi computations.

   Required behavior and fields:
   - `self.df`: full dataframe for the CSV (all roi_id).
   - `self.roi_ids`: sorted list of available roi_id values (must exist; see R1).
   - `self.results_by_roi: dict[int, HeartRatePerRoiResults]`
   - `self.cfg_by_roi: dict[int, HRPlotConfig | dict]` (or a dedicated config type)
     - Stores the exact config used for the most recent analysis of each roi_id.

   Loader:
   - Provide `from_csv(path, *, time_col="time", vel_col="velocity", roi_col="roi_id", **kwargs)`
     - Loads CSV to DataFrame.
     - Must raise if `roi_col` missing (R1).
     - Must normalize roi_id dtype to int (or raise if cannot be coerced).
     - Must set `self.roi_ids` from unique roi_id.

   Running analysis:
   - Provide `run_roi(roi_id, *, cfg: HRPlotConfig | dict | None = None, methods=("lombscargle","welch"))`
     - Validate roi_id exists in `self.roi_ids` (raise if not).
     - Extract t,v for exactly that roi_id.
     - Call existing core analysis free functions in `heart_rate_analysis.py`:
       - `estimate_heart_rate_global(... method="lombscargle")`
       - `estimate_heart_rate_global(... method="welch")`
     - Store:
       - `self.results_by_roi[roi_id] = <per-roi results>`
       - `self.cfg_by_roi[roi_id] = <cfg used>` (store a copy / frozen dataclass instance)
     - Overwrite prior results/config for that roi_id (latest-run-wins) unless ticket implements an explicit history mechanism (not required).

   - Provide `run_all_rois(*, cfg_by_roi: dict[int, HRPlotConfig | dict] | None = None, cfg: HRPlotConfig | dict | None = None, methods=...)`
     - Iterate through all roi_id values and call `run_roi(...)`.
     - Config rules:
       - If `cfg_by_roi` provided and contains roi_id: use that config for that roi_id.
       - Else if `cfg` provided: use that config.
       - Else use defaults.

   Summary:
   - Provide `getSummaryDict()`
     - Returns a JSON-serializable dict containing:
       - per-roi summaries for each roi_id that has been analyzed
         - include both results + agreement + the config used (serialized)
       - aggregate rollup across analyzed roi_id:
         - e.g. list of bpm values by roi_id for lomb & welch
         - count analyzed, count total roi_id in CSV, etc.

   Notes:
   - Do NOT analyze across mixed roi_id.
   - The object can *store* all roi_id, but analysis/plots are per roi_id.

4) Free function `run_hr_analysis(...)` (optional but recommended)
   - Thin wrapper that instantiates `HeartRateAnalysis` and calls `.run_roi(...)` or `.run_all_rois(...)`.
   - Must not duplicate internal logic.
   - Supports:
     - CSV path input
     - direct (time_s, velocity) arrays input **only if** roi_id is also provided (otherwise raise)
   - Document clearly what it returns (analysis object vs per-roi results).

### R3 — Update docstrings and typing
All public functions/classes added must have Google-style docstrings with:
- parameter types and meaning
- defaults explained
- what is returned
- ROI semantics clearly stated
- config-per-roi semantics clearly stated

### R4 — Update runner to demonstrate per-ROI usage (minimal)
Update `run_heart_rate_examples_fixed2.py` to demonstrate using the OO API:
- Load CSV into `HeartRateAnalysis` (must raise clearly if roi_id missing)
- Run analysis for a single roi_id (deterministic default: smallest roi_id)
- Preserve your existing subplot (3,1) plot behavior.
- Do not add CLI switches; keep runner minimal.

Optional (nice-to-have):
- If you already have a per-file config object, show how to pass it into `run_roi(...)`.

### R5 — Add tests under `tests/`
Create `tests/test_heart_rate_pipeline.py`:

- Test that `from_csv` raises if roi_id column is missing.
- Test that `from_csv` loads df and exposes roi_ids.
- Test that `run_roi` stores both `results_by_roi[roi_id]` and `cfg_by_roi[roi_id]`.
- Test that `run_all_rois` can accept `cfg_by_roi` and stores different configs per roi.
- Test that `getSummaryDict()` is JSON-serializable and includes:
  - per-roi entries
  - config-per-roi entries

Tests should run with:
`uv run pytest -q`

If test data is needed:
- Use small synthetic arrays / temporary CSV via pandas in the test.

### R6 — Keep diffs minimal
- No unrelated refactors in `heart_rate_analysis.py`.
- Prefer adding small helper(s) rather than reworking existing functions.

## Acceptance Criteria
- `uv run pytest -q` passes.
- `uv run python run_heart_rate_examples_fixed2.py` still runs and produces plots.
- HeartRateAnalysis:
  - requires roi_id column
  - loads full CSV with multiple roi_id
  - analyzes per roi_id (never mixed)
  - caches results per roi_id
  - caches config per roi_id
  - provides per-roi + aggregate summary dict with configs included

## Notes
Global execution/report rules are defined in:
tickets/CODEX_RULES.md
