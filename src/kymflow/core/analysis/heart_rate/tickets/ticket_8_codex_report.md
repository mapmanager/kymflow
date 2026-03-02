# Ticket 8 Codex Report

## 1) Modified code files
- `heart_rate_pipeline.py`
- `run_heart_rate_examples_fixed2.py`
- `tests/test_heart_rate_pipeline.py`
- `docs/batch_summary_schema.md`

## 2) Artifacts created/updated
- `tickets/ticket_8_codex_report.md`

## 3) Scope confirmation
- Confirmed: no files outside `kymflow/sandbox/heart_rate_analysis/heart_rate/` were modified.
- Confirmed: no files outside ticket 8 **Allowed edits** were modified.

## 4) Unified diff (short)
Note: in this workspace snapshot, these files are untracked by git; short relevant hunks are shown.

### `heart_rate_pipeline.py`
```diff
@@
+AGREE_TOL_BPM_DEFAULT = 30.0
@@ class HeartRateAnalysis:
-def run_roi(..., methods: Sequence[str] = ("lombscargle", "welch"))
+def run_roi(..., methods: Optional[Sequence[str]] = None)
@@
+method_list = ("lombscargle", "welch") if methods is None else tuple(methods)
@@
+def get_roi_df(self, roi_id: int) -> pd.DataFrame: ...
+def get_time_velocity(self, roi_id: int) -> tuple[np.ndarray, np.ndarray]: ...
+def get_roi_results(self, roi_id: int) -> HeartRatePerRoiResults: ...
+def get_roi_summary(self, roi_id: int, *, minimal: bool = True, agree_tol_bpm: float = AGREE_TOL_BPM_DEFAULT) -> dict[str, Any]: ...
@@
+return {
+  "file", "roi_id", "n_total", "n_valid", "valid_frac", "t_min", "t_max",
+  "lomb_bpm", "lomb_hz", "lomb_snr", "welch_bpm", "welch_hz", "welch_snr",
+  "lomb_edge", "welch_edge", "lomb_bc", "welch_bc",
+  "agree_delta_bpm", "agree_ok", "status", "status_note"
+}
@@
+def _classify_status(...):
+    # returns: ok, insufficient_valid, no_peak_lomb, no_peak_welch, method_disagree, other_error
```
Omitted hunks: method bodies for estimator calls and existing summary/aggregate plumbing not directly changed by ticket requirements.

### `run_heart_rate_examples_fixed2.py`
```diff
@@
-import argparse
+from pprint import pprint
@@
-def parse_args() -> argparse.Namespace: ...
-args = parse_args()
+# No CLI parsing; use hard-coded DEFAULT_FILES and dataclass defaults.
@@ def run_one_file(...):
-roi_df = analysis.df[analysis.df[ROI_COL] == roi_id]
-t = roi_df[TIME_COL].to_numpy(dtype=float)
-v = roi_df[VEL_COL].to_numpy(dtype=float)
-summary = analysis.getSummaryDict(...)
-roi_summary = summary["per_roi"].get(str(roi_id), {})
+roi_results = analysis.run_roi(roi_id, cfg=cfg)
+compact_summary = analysis.get_roi_summary(roi_id, minimal=True)
+pprint(compact_summary)
+t, v = analysis.get_time_velocity(roi_id)
+lomb_result = analysis.get_roi_results(roi_id).lomb
+welch_result = analysis.get_roi_results(roi_id).welch
@@
-analysis.run_roi(roi_id, cfg=cfg, methods=("lombscargle", "welch"))
+analysis.run_roi(roi_id, cfg=cfg)
```
Omitted hunks: plotting calls and print formatting unchanged in behavior.

### `tests/test_heart_rate_pipeline.py`
```diff
@@
+def test_helper_methods_get_roi_df_time_velocity_results_and_summary(...): ...
+def test_minimal_summary_has_expected_keys(...): ...
+def test_status_insufficient_valid_for_too_few_samples(...): ...
+def test_status_method_disagree_when_methods_far_apart(...): ...
+def test_runner_no_argparse_dependency(): ...
```
Omitted hunks: existing pre-ticket tests retained.

### `docs/batch_summary_schema.md`
```diff
@@
+# Batch Summary Schema
+Defines keys returned by HeartRateAnalysis.get_roi_summary(..., minimal=True)
+Includes per-method fields, QC (`*_edge`, `*_bc`), agreement logic,
+status enum, and AGREE_TOL_BPM_DEFAULT.
```

## 5) Search confirmation
I searched for runner CLI and dict-get patterns (`parse_args`, `import argparse`, and per-ROI `dict.get` navigation) and updated the ticket 8 runner path to API helper usage. No additional out-of-scope files were modified.

## 6) Validation (commands actually run)
- `python3 -m py_compile heart_rate_pipeline.py run_heart_rate_examples_fixed2.py tests/test_heart_rate_pipeline.py`
- `uv run pytest -q`
- `MPLBACKEND=Agg uv run python run_heart_rate_examples_fixed2.py`

## 7) Expected validation markers
- `uv run pytest -q` should report all tests passing (current run: `14 passed`).
- Runner should execute with no CLI args and print:
  - `FILE: ...`
  - `[Summary] Compact per-ROI summary`
  - keys including `status`, `agree_ok`, `lomb_bpm`, `welch_bpm`.
- Non-interactive backend warning from matplotlib is expected with `MPLBACKEND=Agg`.

## 8) Summary of changes
- Removed CLI parsing dependency from the runner path and used hard-coded/default config flow.
- Added HeartRateAnalysis convenience APIs for ROI dataframe/time-velocity/results/summary access.
- Made `run_roi()` default to running both Lomb-Scargle and Welch when methods are not provided.
- Added minimal stable batch summary schema with agreement and compact status classification.
- Added tests for new APIs/schema/status behavior and runner no-argparse requirement.
- Added batch summary schema documentation.

## 9) Risks / tradeoffs
- `run_all_rois()` and `run_hr_analysis()` still expose `methods`; this keeps backward compatibility but may permit caller divergence from default dual-method behavior.
- Status classification is reason-string driven for some failure modes (`no_peak`, `not_enough_valid_samples`), so upstream reason wording changes could affect labels.
- Runner uses hard-coded `DEFAULT_FILES`; portability depends on local file availability.

## 10) Self-critique
### Pros
- Ticket requirements are implemented with small, targeted API additions.
- Runner is thinner and uses analysis APIs instead of dataframe slicing/dict navigation.
- Validation includes tests and an actual script run.

### Cons
- VCS baseline in this workspace shows files as untracked, so full historical unified diffs are unavailable.
- Runner still contains duplicate `DEFAULT_FILES` assignment, which is pre-existing style debt.

### Drift risk
- Moderate: status logic depends on upstream debug/reason strings and estimator behavior.

### Red flags / architectural violations (if any)
- None identified relative to ticket 8 scope and forbidden-file rules.
