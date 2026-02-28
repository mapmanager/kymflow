# ticket_1.md — Clean up example runner method boundaries (global vs diagnostic)

## Context
We are working ONLY inside:
kymflow/sandbox/heart_rate_analysis/heart_rate/

Goal: fix drift where the example runner prints “Welch” output even when only Lomb–Scargle was computed, and make method boundaries explicit.

This ticket introduces a **diagnostic mode** (CLI flag) that computes/prints/plots Welch **only if actually computed**.

## Scope (STRICT)

### Allowed edits
- run_heart_rate_examples_fixed2.py

### Forbidden edits
- heart_rate_analysis.py
- heart_rate_plots.py
- Any other file in the repo

## Requirements

### R1 — Separate two modes of operation via CLI flag
Add CLI flag:

- `--diagnostic` (default: False)

Behavior:

1) Default mode (no `--diagnostic`)
   - Call `estimate_heart_rate_global(... method="lombscargle")` only.
   - Print ONLY Lomb–Scargle results (or None).
   - Do NOT print “Welch” anything.
   - Do NOT call any Welch plotting functions.

2) Diagnostic mode (`--diagnostic`)
   - Keep the existing global Lomb computation (same as default mode).
   - Additionally compute Welch vs Lomb explicitly using the **existing available API**
     in this folder. Use the function(s) that actually exist (DO NOT invent new APIs).
   - Print both Welch and Lomb estimates (if available) and their difference.
   - Only in this mode, call Welch PSD plot routines (if they exist and if the
     required debug data is available).
   - If Welch cannot be computed with the currently available APIs, print a clear
     message (e.g. “Welch diagnostic not available in current module set”) and
     skip Welch plots—without raising.

### R2 — Preserve local developer modifications (do not revert)
The user has local modifications in `run_heart_rate_examples_fixed2.py`:

- CSV iteration / selection logic has been refactored
- Plots are combined into ONE Matplotlib figure using `plt.subplots(3, 1, ...)`

Do NOT remove or revert these behaviors.

You may reorganize code, but the net behavior must remain:
- Still a (3,1) subplot layout for the three plots
- Still uses the user’s updated CSV selection/iteration logic

### R3 — No fabricated results
Never print a Welch bpm/Hz/SNR line unless Welch was actually computed.

### R4 — Plotting must match computed results
- If only Lomb is computed, only Lomb plot(s) should run.
- If Welch is computed (diagnostic), run both plots.
- Do not call a plot function unless the debug payload needed for it exists.

### R5 — Minimal changes beyond required
Do not redesign the script.
Do not change analysis algorithms.
Only adjust control flow, printing, and conditional plotting.

## Acceptance Criteria
- Running without `--diagnostic`:
  - No reference to Welch in console output.
  - Script completes without error on the existing example CSVs.
- Running with `--diagnostic`:
  - Prints both methods when available, otherwise prints “None” for missing method.
  - Does not crash if Welch cannot be computed (degrades gracefully).
- The script still produces the combined (3,1) subplot layout.

## Notes
Global execution/report rules are defined in:
tickets/CODEX_RULES.md

