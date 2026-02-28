# ticket_7_codex_report.md

## 1) Modified code files
- `heart_rate_pipeline.py`
- `run_heart_rate_examples_fixed2.py`
- `tests/test_heart_rate_pipeline.py`

## 2) Artifacts created
- `docs/pipeline_results_and_config.md`
- `tickets/ticket_7_codex_report.md`

## 3) Scope confirmation
- Confirmed: no files outside `kymflow/sandbox/heart_rate_analysis/heart_rate/` were modified.
- Confirmed: no files outside ticket_7 allowed edit paths were modified.

## 4) Short unified diff for each modified code file

### `heart_rate_pipeline.py`
```diff
@@ class HeartRatePerRoiResults
+    analysis_cfg: HRAnalysisConfig
-    def to_dict(self) -> dict[str, Any]:
+    def to_dict(self, *, compact: bool = False) -> dict[str, Any]:
+        out["analysis_cfg"] = self.analysis_cfg.to_dict()
+        if compact: out["segments_summary"] = {n_windows, n_valid_windows, median_bpm, iqr_bpm, ...}
+        else: out["segments"] = self.segments
@@ class HeartRateAnalysis.__init__
-    self.cfg_by_roi: dict[int, HRAnalysisConfig] = {}
@@ run_roi(...)
-    self.cfg_by_roi[roi_id] = cfg_obj
+    per_roi = HeartRatePerRoiResults(..., analysis_cfg=cfg_obj, ...)
@@ getSummaryDict
- def getSummaryDict(self) -> dict[str, Any]
+ def getSummaryDict(self, *, compact: bool = True) -> dict[str, Any]
- payload["config"] = ...
+ payload = result.to_dict(compact=compact)
```

### `run_heart_rate_examples_fixed2.py`
```diff
@@
+from pprint import pprint
@@ run_one_file(...)
+    compact_summary = analysis.getSummaryDict(compact=True).get("per_roi", {}).get(str(roi_id), {})
+    print("\n[Summary] Compact per-ROI summary")
+    pprint(compact_summary)
```

### `tests/test_heart_rate_pipeline.py`
```diff
@@ test_run_roi_stores_results_and_config
-    assert 1 in analysis.cfg_by_roi
-    assert analysis.cfg_by_roi[1].bpm_band == (200, 700)
+    assert not hasattr(analysis, "cfg_by_roi")
+    assert result.analysis_cfg.bpm_band == (200, 700)
@@ test_run_all_rois_uses_cfg_by_roi
-    assert analysis.cfg_by_roi[1]...
+    assert analysis.results_by_roi[1].analysis_cfg...
@@ test_get_summary_dict...
-    assert "config" in summary["per_roi"]["1"]
+    assert "analysis_cfg" in summary["per_roi"]["1"]
+
+def test_summary_compact_excludes_raw_segments_and_includes_segment_summary(...):
+    compact = analysis.getSummaryDict(compact=True)["per_roi"]["1"]
+    full = analysis.getSummaryDict(compact=False)["per_roi"]["1"]
+    assert "segments" not in compact
+    assert "segments_summary" in compact
+    assert "segments" in full
```

Omitted hunks: docstring updates and unchanged existing logic.

## 5) Search confirmation
- Search run:
  - `rg -n "self\.cfg_by_roi|cfg_by_roi" heart_rate_pipeline.py run_heart_rate_examples_fixed2.py tests/test_heart_rate_pipeline.py`
- Result:
  - `self.cfg_by_roi` references are removed.
  - `cfg_by_roi` remains only as API input for `run_all_rois(...)` / `run_hr_analysis(...)` and in tests using that API (expected by ticket R3).

## 6) Commands actually run
- `python3 -m py_compile /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate/heart_rate_pipeline.py /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate/run_heart_rate_examples_fixed2.py /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate/tests/test_heart_rate_pipeline.py`
- `cd /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate && uv run pytest -q`
- `cd /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate && MPLBACKEND=Agg uv run python run_heart_rate_examples_fixed2.py`
- Searches:
  - `rg -n "self\.cfg_by_roi|cfg_by_roi" ...`
  - `rg -n "analysis_cfg|getSummaryDict\(compact|segments_summary|segments\"" ...`

## 7) Expected validation markers
- `uv run pytest -q` should report:
  - `9 passed`
- Runner command should print:
  - `[Summary] Compact per-ROI summary`
  - `analysis_cfg` inside that summary
  - `segments_summary` key in compact summary (or `None` when segments disabled)

## 8) Summary of changes
- Embedded config directly into per-ROI results via `HeartRatePerRoiResults.analysis_cfg`.
- Removed `HeartRateAnalysis.cfg_by_roi` attribute and all storage/retrieval logic tied to it.
- Updated `run_roi(...)` to persist the exact `HRAnalysisConfig` used inside each per-ROI result.
- Added `getSummaryDict(compact: bool = True)` with compact/full behavior:
  - compact excludes raw segment arrays and includes segment summary stats.
  - full includes raw segment arrays.
- Updated runner to pprint compact summary for selected `ROI_ID`.
- Updated tests for embedded config behavior and compact/full summary behavior.
- Added docs file `docs/pipeline_results_and_config.md`.

## 9) Risks/tradeoffs
- Compact summary computes percentile-based IQR from available segment bpm values; if all windows are invalid, summary fields are `None`.
- Public output shape changed from `config` to `analysis_cfg`; callers relying on old key must migrate.

## 10) Self-critique
### Pros
- Removes config/results drift risk by construction.
- Compact summary materially reduces payload size while preserving useful signal.
- Changes are localized and covered by tests.

### Cons
- Legacy API parameter name `cfg_by_roi` remains (intentionally) and may still be semantically confused with removed internal storage.
- Compact summary currently summarizes only bpm distribution; additional summary metrics could be useful later.

### Drift risk
- Low. Config now travels with results object, reducing synchronization failure modes.

### Red flags
- None identified relative to ticket_7 scope and rules.
