# ticket_2.md — Centralize Welch estimate in core + simplify runner to “run everything”

## Context
Folder boundary (HARD):
kymflow/sandbox/heart_rate_analysis/heart_rate/

We previously introduced `--diagnostic` in the runner to separate “Lomb-only” vs “Welch+Lomb”.
For the next step, we want the runner to be a *simple demo harness* that:
- attempts **both** Lomb–Scargle and Welch global HR estimates every time
- prints/plots only what was actually computed
- contains minimal control flow
- does NOT re-implement Welch logic locally (avoid drift)

## Scope (STRICT)

### Allowed edits
- heart_rate_analysis.py
- run_heart_rate_examples_fixed2.py

### Forbidden edits
- heart_rate_plots.py (do not modify in this ticket)
- Any other file in the repo

## Requirements

### R1 — Add a real Welch global estimate path in `heart_rate_analysis.py`
Implement Welch as a first-class option in the core analysis module **without inventing new external dependencies**.

Acceptable approaches (choose one):
- Extend `estimate_heart_rate_global(..., method="welch")` to support `method="welch"` in addition to `method="lombscargle"`.
  - Must return `(HeartRateEstimate | None, debug_dict)` in the same shape as existing return style.
  - If Welch cannot be computed (insufficient data, too short, etc), return `(None, debug_dict)` with a clear reason field.
OR
- Add a new function `estimate_heart_rate_global_welch(...)` that mirrors the Lomb function’s signature style and return contract.

Implementation MUST:
- Reuse existing Welch helper(s) already present in `heart_rate_analysis.py` (do not duplicate windowing/bandpass/outlier logic if it already exists).
- Clearly document in docstring:
  - expected input (time_s, velocity)
  - what “method=welch” does
  - required debug keys for plotting
  - when it returns None

### R2 — Runner should “run everything” (no diagnostic branching)
Update `run_heart_rate_examples_fixed2.py` so that for each CSV:

1) Compute Lomb–Scargle global HR:
   - via `estimate_heart_rate_global(... method="lombscargle")`

2) Compute Welch global HR:
   - via the new/extended API from R1

3) Print:
   - Lomb result if present; else “None (reason…)”
   - Welch result if present; else “None (reason…)”
   - If both present, print a compact agreement line (e.g., Δbpm, ΔHz, etc.)

4) Plot:
   - Always produce the user’s existing combined Matplotlib figure with `plt.subplots(3, 1, ...)` (must preserve layout).
   - Plot Lomb periodogram when Lomb debug payload is sufficient.
   - Plot Welch PSD when Welch debug payload is sufficient.
   - If one method is None, skip that method’s plot and write a small text note to console (no exceptions).

Remove or ignore CLI branching (`--diagnostic`) if it still exists:
- It is fine to keep argparse for other reasons, but the HR computation should not depend on `--diagnostic`.

### R3 — Preserve user edits in runner
The user has local modifications in `run_heart_rate_examples_fixed2.py` that MUST remain:
- refactored CSV selection/iteration logic (hard-coded paths are OK)
- combined plot layout using `plt.subplots(3, 1, ...)`

This ticket must not revert those behaviors.

### R4 — No fabricated outputs
Never print a Welch bpm/Hz/SNR line unless Welch was actually computed.
Never call Welch plot function unless Welch debug payload exists.

### R5 — Keep diffs minimal
- No unrelated refactors.
- No reformatting outside touched code.
- Keep changes focused on adding Welch support to the core and simplifying the runner.

## Acceptance Criteria
- `uv run python run_heart_rate_examples_fixed2.py` runs without error.
- For the known example CSVs:
  - Lomb and Welch sections are both attempted and reported.
  - If Welch cannot be computed for a file, runner does not crash and output clearly indicates why.
- The (3,1) subplot layout is preserved.
- Runner does not contain custom Welch-estimation logic duplicating the core (i.e., no runner-local Welch implementation beyond calling the core API).

## Notes
Global execution/report rules are defined in:
tickets/CODEX_RULES.md
