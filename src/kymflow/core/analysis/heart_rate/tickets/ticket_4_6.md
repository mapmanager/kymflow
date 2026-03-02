# ticket_4_6.md — QC metrics + edge handling + segment analysis/plots (config-controlled) + runner ROI constant

## Context

We are working inside:

- `kymflow/sandbox/heart_rate_analysis/heart_rate/`

This ticket introduces quality/confidence metrics, edge-handling, and (re)enables segment-based analysis/plotting behind configuration, while also making ROI selection explicit in the runner.

## Goals (high level)

1. **Add confidence/quality metrics** to HR estimates (Lomb–Scargle and Welch):
   - store in result dataclasses
   - appear in summary dicts
   - optionally annotate plots
2. **Edge handling**: identify when the best peak is near band edges and mark as low-trust.
3. **Segment HR analysis** (time-local HR) is **available but config-controlled** so normal runs stay fast.
4. **Runner**: require an explicit `ROI_ID` constant at top (no auto “pick smallest ROI”).
5. **Docs + tests**: add/update docs under `docs/`, add tests under `tests/`.

## Scope (STRICT)

### Allowed edits

Codex may edit ONLY these paths:

- `kymflow/sandbox/heart_rate_analysis/heart_rate/heart_rate_analysis.py`
- `kymflow/sandbox/heart_rate_analysis/heart_rate/heart_rate_pipeline.py`
- `kymflow/sandbox/heart_rate_analysis/heart_rate/heart_rate_plots.py`
- `kymflow/sandbox/heart_rate_analysis/heart_rate/run_heart_rate_examples_fixed2.py`
- `kymflow/sandbox/heart_rate_analysis/heart_rate/tests/` (may add/modify tests)
- `kymflow/sandbox/heart_rate_analysis/heart_rate/docs/` (may add/modify markdown docs)
- `kymflow/sandbox/heart_rate_analysis/heart_rate/tickets/` (report file only)

### Forbidden edits

- Any file outside `kymflow/sandbox/heart_rate_analysis/heart_rate/`
- Any refactor that changes external meaning of existing enum/string values
- Any change that removes the existing Matplotlib plotting style in `heart_rate_plots.py` where plot fns accept `ax: Optional[plt.Axes] = None`

## Rationale: what “segment analysis/plotting” is and why it exists

Segment analysis means computing HR estimates on **time windows** (e.g., 2–4 s windows stepped by 0.5–1 s). This is useful for:

- **QC / stationarity check**: if HR varies wildly over time, your “global” HR may be unreliable.
- **missing-data robustness**: some windows may be invalid; seeing a time series highlights where the signal is usable.
- **artifact isolation**: motion/radon failures can contaminate global HR; segment results show contamination is localized.

It is not strictly required to produce a single global HR number, but it is very valuable for debugging and quality control. Because it can be slower (many window computations), it should be **config-controlled**.

## Requirements

### R1 — Add structured QC metrics to HR estimates

Add fields to the relevant result objects so both Welch and Lomb results can carry QC.

Minimum set (per estimate):

- `edge_flag: bool` — True if peak lies near band edge.
- `edge_hz_distance: float | None` — distance from nearest edge in Hz (or None if unknown).
- `band_concentration: float | None` — fraction of power concentrated near the peak (definition below).
- `snr: float` — already present; keep.
- `method: str` — already present; keep.

Definitions (implement consistently for both methods):

- **Edge flagging**
  - Let `band_hz = (lo, hi)` derived from bpm band.
  - Let `edge_margin_hz = max(0.2, 0.05*(hi-lo))` (configurable).
  - If `f_peak <= lo + edge_margin_hz` OR `f_peak >= hi - edge_margin_hz` then `edge_flag=True`.
- **Band concentration**
  - Compute total band power and “peak neighborhood” power.
  - Peak neighborhood: `|f - f_peak| <= peak_half_width_hz` (configurable, default 0.5 Hz).
  - `band_concentration = peak_neighborhood_power / total_band_power` (guard against divide by zero).

Where to store:
- In core estimate dataclass (preferred) or in pipeline result wrapper if core dataclass should stay minimal.
- Must be visible in `getSummaryDict()` under each method.

### R2 — Configuration: introduce QC/segment controls without CLI dependence

Add config fields (likely in `HRPlotConfig` and/or a new analysis config object):

- `edge_margin_hz: float = 0.5` (or computed default)
- `peak_half_width_hz: float = 0.5`
- `do_segments: bool = False` (default off)
- `seg_win_sec: float = 6.0` (or similar; pick sensible default)
- `seg_step_sec: float = 1.0`
- `seg_min_valid_frac: float = 0.5` (minimum fraction of finite samples in a window)

No new CLI args required. Runner should use config defaults unless user edits the dataclass defaults.

### R3 — Reactivate the segment analysis path behind `cfg.do_segments`

If the runner currently has disabled code (e.g., under `if 0:`) for segment plotting/import:

- Replace that with `if cfg.do_segments: ...`
- Ensure it uses the existing functions in `heart_rate_analysis.py` (or add a minimal helper) to compute per-window estimates.

Segment computation should return a clean structure, e.g.:

- arrays/lists of `t_center`, `bpm`, `snr`, `valid_frac`, plus method label.

### R4 — Plots: optionally annotate QC and add segment plot

1) Existing plots must remain callable with `ax: Optional[plt.Axes] = None` and return `Axes`.
2) Add plot annotations (in title or a small text box) for:
   - bpm, snr
   - edge_flag (e.g., “EDGE” warning)
   - band_concentration

3) Add a new plot function (or reuse existing disabled one) for segment HR:
   - x = time (s) (window center)
   - y = bpm
   - Optionally show invalid windows as gaps
   - This is a QC plot, not the primary result.

### R5 — Runner: explicit ROI_ID constant, no “pick smallest ROI”

In `run_heart_rate_examples_fixed2.py`:

- Add near top:

  - `ROI_ID: int = 1`

- Before analysis:
  - Validate that `ROI_ID` exists in the loaded CSV’s roi_ids.
  - If not, raise a clear error.

No implicit default selection (no `min(roi_ids)` etc).

### R6 — Tests

Add/extend tests under `tests/` to cover:

- QC metric computation presence in summaries (at least keys exist and types sane).
- Edge flagging behavior with synthetic signals near band edge.
- Segment computation respects `do_segments` flag and returns expected shapes.

Use `uv run pytest -q` as the test command.

### R7 — Docs

Create/update docs in `docs/`:

- `docs/heart_rate_qc_metrics.md` describing each QC metric and interpretation.
- `docs/heart_rate_segments.md` describing segment HR and how to interpret it.

Keep docs short but precise.

## Acceptance criteria

- `uv run python run_heart_rate_examples_fixed2.py` runs and:
  - uses ROI_ID=1 (or user-edited constant) and errors clearly if missing
  - prints Lomb + Welch summaries as before
  - does NOT run segment analysis unless `cfg.do_segments=True`
- Plots still appear in the existing user layout and do not break the `ax=...` API pattern.
- `uv run pytest -q` passes.

## Codex implementation report (REQUIRED)

Save as:

- `kymflow/sandbox/heart_rate_analysis/heart_rate/tickets/ticket_4_6_codex_report.md`

Report MUST include:

1. **Modified code files** (exclude the report file itself; list that under “Artifacts created”)
2. **Artifacts created** (including this report)
3. **Scope confirmation**: confirm no edits outside allowed paths
4. **Short unified diff** for each modified *code* file (keep it concise)
5. **Search confirmation**: state what you searched for (e.g., `rg -n "if 0:|segments|min\(analysis\.roi_ids\)" ...`) and what you found/changed
6. **Commands actually run** (include exact commands)
7. **Summary of changes**
8. **Risks/tradeoffs**
9. **Self-critique** (pros/cons/drift risk/red flags)
