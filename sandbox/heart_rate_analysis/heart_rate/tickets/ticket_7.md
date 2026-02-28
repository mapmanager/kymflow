# ticket_7.md — Merge per-ROI config into results + add compact summary option

## Context
Folder boundary (HARD):
kymflow/sandbox/heart_rate_analysis/heart_rate/

Current architecture (after ticket_3 and ticket_4_6) has:
- `HeartRateAnalysis.results_by_roi: dict[int, HeartRatePerRoiResults]`
- `HeartRateAnalysis.cfg_by_roi: dict[int, HRAnalysisConfig]`

We want to remove the possibility of config/results drift by embedding the exact config used for a run
inside the per-ROI results object.

We also want `getSummaryDict()` to support a compact mode so callers can avoid huge outputs
(e.g., raw segment time-series arrays).

## Scope (STRICT)

### Allowed edits
- heart_rate_pipeline.py
- run_heart_rate_examples_fixed2.py
- tests/ (add/modify tests)
- docs/ (add/modify markdown docs)

### Forbidden edits
- heart_rate_analysis.py (do not modify in this ticket)
- heart_rate_plots.py (do not modify in this ticket)
- Any other file in the repo

## Requirements

### R1 — Embed config in `HeartRatePerRoiResults`
Update the `HeartRatePerRoiResults` dataclass to include:

- `analysis_cfg: HRAnalysisConfig`

Rules:
- This must be the exact config used for that ROI’s most recent `run_roi(...)`.
- It must be included in `.to_dict()` serialization.
- It must be included in `getSummaryDict()` output (both compact and full).

### R2 — Remove `cfg_by_roi` from `HeartRateAnalysis`
Update `HeartRateAnalysis` to remove:

- `self.cfg_by_roi`

All code should use `results_by_roi[roi_id].analysis_cfg` to retrieve the config used.

### R3 — Update `run_roi` and `run_all_rois` storage
Update `HeartRateAnalysis.run_roi(...)`:
- Ensure it constructs `HeartRatePerRoiResults(..., analysis_cfg=<cfg_used>, ...)`
- Store only `self.results_by_roi[roi_id] = per_roi_results`
- Do not store config separately.

Update `run_all_rois(...)`:
- Ensure per-ROI config selection logic remains the same (cfg_by_roi override, else cfg, else default),
  but the chosen config is embedded into each per-ROI results object.

### R4 — Compact summary option for `getSummaryDict`
Update `HeartRateAnalysis.getSummaryDict(...)` to accept:

- `compact: bool = True`

Behavior:
- When `compact=True`:
  - Include global estimates, QC metrics, agreement, and analysis_cfg.
  - Do NOT include raw per-window segment arrays/series (if present).
  - Instead, include a small segment summary if segment results exist, e.g.:
    - `n_windows`, `n_valid_windows`, `median_bpm`, `iqr_bpm` (method-specific if needed)

- When `compact=False`:
  - Include everything (including segment series) as currently returned.

Docstring MUST:
- describe the difference between compact and full outputs

### R5 — Runner: pprint compact summary
In `run_heart_rate_examples_fixed2.py`:
- pprint the compact summary for `ROI_ID` (do not dump the full summary by default).
- Keep runner behavior and plotting intact otherwise.

### R6 — Tests
Update/add tests to cover:
- `cfg_by_roi` no longer exists and config is present in per-ROI results.
- `.to_dict()` includes `analysis_cfg` serialization.
- `getSummaryDict(compact=True)` excludes raw segment arrays but includes segment summary keys.
- `getSummaryDict(compact=False)` includes raw segment arrays when segments exist.

Run with:
- `uv run pytest -q`

### R7 — Docs
Add/update docs in `docs/`:
- `docs/pipeline_results_and_config.md` describing:
  - where config is stored (embedded in per-ROI results)
  - how to interpret compact vs full summaries

## Acceptance Criteria
- `uv run pytest -q` passes.
- `uv run python run_heart_rate_examples_fixed2.py` runs and prints a compact summary for ROI_ID.
- No remaining references to `cfg_by_roi`.
- `getSummaryDict(compact=True)` avoids large raw segment arrays but still reports meaningful segment summary.

## Codex implementation report (REQUIRED)
Save as:

- `kymflow/sandbox/heart_rate_analysis/heart_rate/tickets/ticket_7_codex_report.md`

Report MUST include:
1) Modified code files (exclude the report file itself; list that under “Artifacts created”)
2) Artifacts created (including this report)
3) Scope confirmation: confirm no edits outside allowed paths
4) Short unified diff for each modified code file
5) Search confirmation (e.g., search for `cfg_by_roi` and confirm all references removed)
6) Commands actually run (include exact commands)
7) Expected validation markers
8) Summary of changes
9) Risks/tradeoffs
10) Self-critique (pros/cons/drift risk/red flags)

Global rules:
- Follow `tickets/CODEX_RULES.md`
