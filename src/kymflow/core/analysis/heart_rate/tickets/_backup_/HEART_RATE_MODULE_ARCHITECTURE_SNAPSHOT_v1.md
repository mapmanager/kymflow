# Heart Rate Module Architecture Snapshot v1

Location scope (STRICT EDIT BOUNDARY):
kymflow/sandbox/heart_rate_analysis/heart_rate/

This document defines the architectural baseline for all ticket-driven edits.
Codex MUST NOT modify code outside this folder.

------------------------------------------------------------
SYSTEM PURPOSE
------------------------------------------------------------

This subsystem is a standalone heart-rate (HR) analysis pipeline based on velocity traces.

It is independent from stall detection and other imaging-core subsystems.

The pipeline provides:

1) Global HR estimation (Lomb–Scargle primary method)
2) Optional Welch spectral analysis
3) Cross-method agreement diagnostics
4) Confidence metrics
5) Sliding-window HR vs time
6) Plotting utilities
7) Example runner script

------------------------------------------------------------
FILE RESPONSIBILITIES
------------------------------------------------------------

heart_rate_analysis.py
----------------------
Core signal-processing layer.

Owns:
- estimate_heart_rate_global()
- spectral estimation (Welch / Lomb–Scargle)
- preprocessing (winsorize, detrend, bandpass)
- frequency-domain peak detection
- HeartRateEstimate dataclass

Does NOT:
- Perform sliding-window HR
- Compute advanced confidence metrics
- Perform plotting
- Print user-facing summaries

------------------------------------------------------------

heart_rate_advanced_analysis.py
--------------------------------
Advanced analysis layer.

Owns:
- compute_cross_method_agreement()
- compute_hr_confidence()
- sliding_window_hr()
- HRConfidence dataclass
- HRWindowEstimate dataclass

Consumes:
- Core analysis functions

Does NOT:
- Perform plotting
- Print summaries

------------------------------------------------------------

heart_rate_plots.py
-------------------
Core plotting utilities.

Owns:
- plot_hr_psd_welch()
- plot_hr_periodogram_lombscargle()

Does NOT:
- Compute HR
- Modify analysis outputs

------------------------------------------------------------

heart_rate_advanced_plots.py
----------------------------
Advanced visualization layer.

Owns:
- plot_confidence_metrics()
- plot_sliding_window_hr()
- plot_window_data_coverage()

Does NOT:
- Perform analysis

------------------------------------------------------------

run_heart_rate_examples_fixed2.py
---------------------------------
Example driver script.

Owns:
- Loading CSV
- Calling analysis functions
- Printing results
- Calling plotting functions

Must:
- Never fabricate results
- Only print outputs that were actually computed
- Keep method boundaries explicit

------------------------------------------------------------
KNOWN DRIFT ISSUES (TO BE CLEANED)
------------------------------------------------------------

1) Example runner prints “Welch” results even when only Lomb–Scargle was computed.
2) Plot functions exist for both methods, but runner does not consistently compute both.
3) Responsibility boundaries between global estimation and cross-method agreement are blurred in console output.

------------------------------------------------------------
ARCHITECTURAL PRINCIPLES
------------------------------------------------------------

1) Single Responsibility:
   Each file owns a specific layer.

2) No Fabricated Output:
   Example runner must not print results from methods not executed.

3) Explicit Method Calls:
   If Welch is desired, compute it explicitly via cross-method function.

4) Strict Folder Boundary:
   Codex edits ONLY within:
   kymflow/sandbox/heart_rate_analysis/heart_rate/

5) Moderate Cleanup Allowed:
   - Small structural improvements allowed
   - API signatures MAY change
   - Backwards compatibility NOT required
   - Public behavior stability NOT required
   - Print format may change if justified

------------------------------------------------------------
TICKET SYSTEM RULES
------------------------------------------------------------

Tickets must:

- Be numbered (e.g., ticket_1.md, ticket_1_2.md)
- Define scope explicitly
- Define files allowed to change
- Define files forbidden to change
- Define acceptance criteria
- Require Codex to generate:

    1) Diff summary
    2) List of modified files
    3) Confirmation no edits outside allowed folder
    4) Self-critique:
        - Pros of the change
        - Cons or tradeoffs
        - Drift risk
        - Red flags
        - Architectural violations (if any)

------------------------------------------------------------
END SNAPSHOT v1
------------------------------------------------------------