# ticket_2_codex_report.md

## 1) Modified code files
- `heart_rate_analysis.py`
- `run_heart_rate_examples_fixed2.py`

## 2) Artifacts created/updated
- `tickets/ticket_2_codex_report.md`

## 3) Scope confirmation
- Confirmed: no files outside `kymflow/sandbox/heart_rate_analysis/heart_rate/` were modified.
- Confirmed: no files outside this ticket's **Allowed edits** list were modified.

## 4) Unified diff (short)

### `heart_rate_analysis.py`
```diff
--- a/heart_rate_analysis.py
+++ b/heart_rate_analysis.py
@@
 def estimate_heart_rate_global(
@@
-    lomb_n_freq: int = 512,
+    lomb_n_freq: int = 512,
+    interp_max_gap_sec: float = 0.05,
+    bandpass_order: int = 3,
+    nperseg_sec: float = 2.0,
 ) -> tuple[Optional[HeartRateEstimate], dict]:
-    """Estimate HR from the full trace (robust to missing values).
+    """Estimate global HR from full-trace velocity samples.
@@
+    if method.lower() == "welch":
+        try:
+            x_interp = interpolate_small_gaps(t, x0, max_gap_sec=interp_max_gap_sec)
+            m_welch = np.isfinite(t) & np.isfinite(x_interp)
+            n_valid_welch = int(np.sum(m_welch))
+            if n_valid_welch < 256:
+                return None, {"reason": "not_enough_valid_samples_after_interp", ...}
+
+            fs = estimate_fs(t[m_welch])
+            xf = bandpass_filter(x_interp[m_welch], fs, band_hz=band_hz, order=bandpass_order)
+            nperseg = int(np.clip(round(fs * nperseg_sec), 128, 8192))
+            f_peak, snr, f, Pxx = dominant_freq_welch(xf, fs, band_hz=band_hz, nperseg=nperseg)
+            if not np.isfinite(f_peak):
+                return None, {"reason": "no_welch_peak_in_band", ...}
+
+            est = HeartRateEstimate(..., method="welch")
+            dbg = {"f": f, "Pxx": Pxx, ...}
+            return est, dbg
+        except Exception as e:
+            return None, {"reason": f"welch_failed: {e}", ...}
```
Omitted hunks: detailed debug payload dictionaries and expanded docstring lines were shortened here for brevity.

### `run_heart_rate_examples_fixed2.py`
```diff
--- a/run_heart_rate_examples_fixed2.py
+++ b/run_heart_rate_examples_fixed2.py
@@
-from typing import Optional
@@
-from heart_rate_analysis import (
-    HeartRateEstimate,
-    estimate_fs,
-    estimate_heart_rate_global,
-    estimate_heart_rate_segments,
-    winsorize_mad,
-    detrend_finite,
-    interpolate_small_gaps,
-    bandpass_filter,
-    dominant_freq_welch,
-)
+from heart_rate_analysis import (
+    estimate_heart_rate_global,
+    estimate_heart_rate_segments,
+)
@@
-def run_one_file(csv_path: Path, *, cfg: HRPlotConfig, diagnostic: bool = False) -> None:
+def run_one_file(csv_path: Path, *, cfg: HRPlotConfig) -> None:
@@
-    # Analysis: global HR (Lomb always; Welch in diagnostic mode)
+    # Analysis: global HR (run both methods every time)
@@
+    est_welch, dbg_welch = estimate_heart_rate_global(... method="welch", ...)
@@
-    if diagnostic:
-        est_welch, welch_error = _estimate_welch_diagnostic(...)
+    if est_welch is None:
+        print(f"  Welch:         None ({reason})")
+    else:
+        print(f"  Welch:         {est_welch.bpm:.1f} bpm ...")
+    if (est_ls is not None) and (est_welch is not None):
+        print(f"  Agreement:     Δbpm={diff_bpm:+.1f}, ΔHz={diff_hz:+.3f}")
@@
-    if diagnostic and (est_welch is not None):
+    if (est_welch is not None) and ("f" in dbg_welch) and ("Pxx" in dbg_welch):
         plot_hr_psd_welch(...)
@@
-    try:
-        plot_hr_periodogram_lombscargle(...)
-    except Exception as e:
-        print(f"  Lomb–Scargle plot skipped: {e}")
+    if (est_ls is not None) and ("f_grid" in dbg_ls) and ("power" in dbg_ls):
+        plot_hr_periodogram_lombscargle(...)
+    else:
+        print("  Lomb–Scargle plot skipped: Lomb estimate/debug unavailable.")
@@
-def _estimate_welch_diagnostic(...):
-    ...
-
@@
-    p.add_argument("--diagnostic", ...)
@@
-        run_one_file(p, cfg=cfg, diagnostic=bool(args.diagnostic))
+        run_one_file(p, cfg=cfg)
```
Omitted hunks: unchanged plotting layout and untouched CSV-selection logic were omitted.

## 5) Search confirmation
- I searched for other occurrences of the ticket patterns (`diagnostic` branching and runner-local Welch implementation) with:
  - `rg -n "diagnostic|_estimate_welch_diagnostic" kymflow/sandbox/heart_rate_analysis/heart_rate`
- Results were only in ticket/docs artifacts and not in executable runner code after this change, so no additional code edits were needed.

## 6) Summary of changes
- Added first-class Welch support to `estimate_heart_rate_global(..., method="welch")`.
- Welch path now returns `(HeartRateEstimate | None, debug_dict)` with explicit `reason` on failure.
- Welch debug payload includes plotting-relevant keys (`f`, `Pxx`) when available.
- Runner now always attempts both Lomb and Welch for each CSV (no diagnostic branching in HR computation).
- Runner prints method-specific `None (reason)` messages when a method cannot be computed.
- Runner prints a compact agreement line (`Δbpm`, `ΔHz`) when both estimates are present.
- Runner no longer contains custom Welch-estimation logic.
- Plot calls are now gated by computed estimate + debug payload sufficiency checks.

## 7) Risks / tradeoffs
- Global Welch path introduces additional optional parameters in `estimate_heart_rate_global`; callers using defaults are unaffected, but behavior now depends on interpolation/bandpass defaults for Welch.
- Runner gates plotting by debug-key presence before calling plot functions, which is conservative and may skip plotting if future debug contracts change.
- Full end-to-end run with GUI plots was not executed in this pass; only syntax and CLI validation were run.

## 8) Self-critique
### Pros
- Welch implementation is centralized in core analysis, eliminating runner-local duplication.
- Runner control flow is simpler and always “runs everything.”
- Output/plot behavior now strictly matches what was actually computed.

### Cons
- The runner still imports `plot_hr_segment_estimates` while segment plotting remains disabled (`if 0`), which is pre-existing but still noisy.
- Debug contract is implicit dict keys rather than typed structure.

### Drift risk
- Low to moderate: centralized Welch in core reduces drift versus ticket 1, but debug-key contracts are still string-key based.

### Red flags / architectural violations (if any)
- None detected relative to ticket scope and `CODEX_RULES.md`.

## Validation run
- `python3 -m py_compile heart_rate_analysis.py run_heart_rate_examples_fixed2.py` (passed)
- `uv run python run_heart_rate_examples_fixed2.py --help` (passed)
- Manual full run command:
  - `uv run python run_heart_rate_examples_fixed2.py`
