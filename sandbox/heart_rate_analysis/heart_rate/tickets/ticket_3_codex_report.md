# ticket_3_codex_report.md

## 1) Modified code files
- `heart_rate_pipeline.py` (new)
- `run_heart_rate_examples_fixed2.py`
- `tests/test_heart_rate_pipeline.py` (new)

## 2) Artifacts created/updated
- `tickets/ticket_3_codex_report.md`

## 3) Scope confirmation
- Confirmed: no files outside `kymflow/sandbox/heart_rate_analysis/heart_rate/` were modified.
- Confirmed: no files outside ticket_3 **Allowed edits** were modified.

## 4) Unified diff (short)

### `heart_rate_pipeline.py` (new)
```diff
+++ heart_rate_pipeline.py
+@dataclass(frozen=True)
+class HRAnalysisConfig:
+    ...
+
+@dataclass(frozen=True)
+class HeartRateResults:
+    ...
+
+@dataclass(frozen=True)
+class HeartRatePerRoiResults:
+    ...
+
+class HeartRateAnalysis:
+    @classmethod
+    def from_csv(...):
+        # requires roi_id, normalizes to int
+
+    def run_roi(...):
+        # analyzes exactly one roi_id via estimate_heart_rate_global(...)
+        # caches results_by_roi and cfg_by_roi
+
+    def run_all_rois(...):
+        # cfg_by_roi override -> cfg -> defaults
+
+    def getSummaryDict(self):
+        # per-roi + aggregate JSON-serializable summary with config
+
+def run_hr_analysis(...):
+    # wrapper for CSV mode and array mode; array mode requires roi_id
```
Omitted hunks: full dataclass fields/docstrings and helper `_coerce_roi_to_int`.

### `run_heart_rate_examples_fixed2.py`
```diff
--- a/run_heart_rate_examples_fixed2.py
+++ b/run_heart_rate_examples_fixed2.py
@@
-from heart_rate_analysis import estimate_heart_rate_global, ...
+from heart_rate_pipeline import HeartRateAnalysis
@@
-def load_time_velocity(...):
-    ...
-
 def run_one_file(csv_path: Path, *, cfg: HRPlotConfig) -> None:
-    t, v = load_time_velocity(csv_path)
+    analysis = HeartRateAnalysis.from_csv(csv_path, time_col=..., vel_col=..., roi_col=...)
+    roi_id = int(min(analysis.roi_ids))
+    roi_results = analysis.run_roi(roi_id, cfg=cfg, methods=("lombscargle", "welch"))
+    df_roi = analysis.df[analysis.df[ROI_COL] == roi_id]
+    t = df_roi[TIME_COL].to_numpy(dtype=float)
+    v = df_roi[VEL_COL].to_numpy(dtype=float)
@@
-    est_ls, dbg_ls = estimate_heart_rate_global(...)
-    est_welch, dbg_welch = estimate_heart_rate_global(...)
+    lomb_result = roi_results.lomb
+    welch_result = roi_results.welch
+    dbg_ls = {} if lomb_result is None else lomb_result.debug
+    dbg_welch = {} if welch_result is None else welch_result.debug
@@
-    if (est_ls is not None) and (est_welch is not None):
-        ...
+    if roi_results.agreement is not None:
+        print("Agreement ...")
```
Omitted hunks: unchanged plotting layout and existing argparse options.

### `tests/test_heart_rate_pipeline.py` (new)
```diff
+++ tests/test_heart_rate_pipeline.py
+def test_from_csv_raises_when_roi_missing(...)
+def test_from_csv_loads_df_and_roi_ids(...)
+def test_run_roi_stores_results_and_config(...)
+def test_run_all_rois_uses_cfg_by_roi(...)
+def test_get_summary_dict_json_serializable_and_contains_config(...)
```
Omitted hunks: synthetic CSV fixtures and fake estimator helper.

## 5) Search confirmation
- I searched for ROI/pipeline integration points with:
  - `rg -n "load_time_velocity|HeartRateAnalysis\.from_csv|run_roi\(|roi_id" ...`
- I found and updated only the runner/test/pipeline locations needed for ticket_3.
- I did not modify `heart_rate_plots.py` or unrelated files.

## 6) Validation (commands actually run)
- `python3 -m py_compile /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate/heart_rate_pipeline.py /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate/run_heart_rate_examples_fixed2.py /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate/tests/test_heart_rate_pipeline.py`
- `cd /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate && uv run pytest -q`
- `cd /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate && uv run python run_heart_rate_examples_fixed2.py --help`

Results:
- `py_compile`: passed
- `uv run pytest -q`: passed (`5 passed, 1 warning`)
- runner `--help`: passed

## 7) Expected validation markers
- `uv run pytest -q` should show:
  - `5 passed`
- `uv run python run_heart_rate_examples_fixed2.py --help` should print argparse usage and exit code 0.
- A full runner execution (`uv run python run_heart_rate_examples_fixed2.py`) should print:
  - `selected roi_id: <smallest>`
  - `Lomb–Scargle: ...` or `None (reason)`
  - `Welch: ...` or `None (reason)`
  - optional `Agreement: Δbpm=..., ΔHz=...`
  - and still render a combined `(3,1)` plot figure.

## 8) Summary of changes
- Added OO module `heart_rate_pipeline.py` with:
  - `HRAnalysisConfig`
  - `HeartRateResults`
  - `HeartRatePerRoiResults`
  - `HeartRateAnalysis` class
  - `run_hr_analysis` wrapper
- Enforced `roi_id` presence and integer coercion in CSV loading.
- Implemented per-ROI analysis and caching (`results_by_roi`, `cfg_by_roi`).
- Implemented `run_all_rois` with per-ROI config override precedence.
- Implemented JSON-serializable per-ROI + aggregate summary via `getSummaryDict()`.
- Updated runner to demonstrate OO usage by loading CSV with `HeartRateAnalysis`, selecting smallest ROI, and running analysis through `run_roi(...)` while preserving existing `(3,1)` plotting behavior.
- Added unit tests for loader errors, ROI discovery, per-ROI caching, per-ROI configs, and summary serialization.

## 9) Risks / tradeoffs
- New pipeline uses dict-based debug payload passthrough from core estimates; if debug key contracts change in the core estimator, downstream consumers should tolerate missing keys.
- Runner now depends on `heart_rate_pipeline.py`; this is intentional but increases coupling between demo script and new OO layer.
- Existing warning from repo pytest config (`Unknown config option: main_file`) remains unchanged and outside ticket scope.

## 10) Self-critique
### Pros
- Implements ROI-safe analysis semantics explicitly.
- Centralizes per-ROI state and config caching in one object.
- Uses existing core free functions for Lomb/Welch (no algorithm duplication).
- Added focused tests that validate ticket-critical behavior.

### Cons
- Runner module docstring still contains some historical context and could be further trimmed in a future cleanup ticket.
- Tests use monkeypatched estimator for stability; they validate pipeline orchestration more than spectral correctness.

### Drift risk
- Low to moderate. Pipeline orchestration is centralized, but long-term drift can occur if estimator debug payload conventions evolve.

### Red flags / architectural violations (if any)
- None identified relative to `ticket_3.md` and `tickets/CODEX_RULES.md`.
