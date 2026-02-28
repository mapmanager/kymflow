# ticket_4_6_codex_report.md

## 1) Modified code files
- `heart_rate_analysis.py`
- `heart_rate_pipeline.py`
- `heart_rate_plots.py`
- `run_heart_rate_examples_fixed2.py`
- `tests/test_heart_rate_pipeline.py`

## 2) Artifacts created/updated
- `docs/heart_rate_qc_metrics.md`
- `docs/heart_rate_segments.md`
- `tickets/ticket_4_6_codex_report.md`

## 3) Scope confirmation
- Confirmed: no files outside `kymflow/sandbox/heart_rate_analysis/heart_rate/` were modified.
- Confirmed: no files outside ticket_4_6 allowed edit paths were modified.

## 4) Unified diff (short)

### `heart_rate_analysis.py`
```diff
@@ class HeartRateEstimate
-    method: str
+    method: str
+    edge_flag: bool = False
+    edge_hz_distance: Optional[float] = None
+    band_concentration: Optional[float] = None
@@ estimate_heart_rate_global(...)
+    edge_margin_hz: Optional[float] = None,
+    peak_half_width_hz: float = 0.5,
@@ lomb/welch branches
+    edge_flag, edge_hz_distance, band_concentration = _compute_qc_metrics_from_spectrum(...)
+    HeartRateEstimate(..., edge_flag=..., edge_hz_distance=..., band_concentration=...)
+    dbg includes edge_flag/edge_hz_distance/band_concentration
@@
+def estimate_heart_rate_segment_series(..., seg_win_sec, seg_step_sec, seg_min_valid_frac) -> dict[str, np.ndarray]:
+    # windowed segment HR series for QC; returns t_center/bpm/snr/valid_frac/edge_flag/band_concentration
```

### `heart_rate_pipeline.py`
```diff
@@ HRAnalysisConfig
+    edge_margin_hz, peak_half_width_hz
+    do_segments, seg_win_sec, seg_step_sec, seg_min_valid_frac
@@ HeartRateResults
+    edge_flag, edge_hz_distance, band_concentration
@@ HeartRatePerRoiResults
+    segments: Optional[dict[str, list[float]]] = None
@@ run_roi(...)
+    passes edge/QC config through estimate_heart_rate_global(...)
+    if cfg.do_segments: compute estimate_heart_rate_segment_series(...) and store in per-roi results
@@ run_hr_analysis(...)
-    selected_roi = min(analysis.roi_ids) when roi_id not provided
+    explicit roi_id now required when run_all=False
```

### `heart_rate_plots.py`
```diff
@@ HRPlotConfig
+    edge_margin_hz, peak_half_width_hz
+    do_segments, seg_win_sec, seg_step_sec, seg_min_valid_frac
@@ existing plot functions
- ) -> None
+ ) -> plt.Axes
+ return ax
+ add small QC annotation text box (bpm/snr/edge/band_concentration) on Welch and Lomb plots
@@
+def plot_hr_segment_series(t_center, bpm, *, title="", ax: Optional[plt.Axes] = None) -> plt.Axes
```

### `run_heart_rate_examples_fixed2.py`
```diff
@@ constants
+ROI_ID: int = 1
@@ run_one_file
-    roi_id = min(analysis.roi_ids)
+    validate ROI_ID exists; raise clear error if missing
+    roi_id = ROI_ID
@@ output
+    print QC fields for Lomb/Welch (edge flag + band concentration)
@@ segments path
-    if 0:
+    if cfg.do_segments:
+        print segment QC summary
+        optional segment QC plot via plot_hr_segment_series(...)
```

### `tests/test_heart_rate_pipeline.py`
```diff
+def test_qc_metrics_keys_present_in_summary(...)
+def test_edge_flag_true_for_peak_near_band_edge(...)
+def test_segments_respect_do_segments_flag(...)
```

Omitted hunks: non-functional docstring expansions and full helper implementations for brevity.

## 5) Search confirmation
- I searched for ticket-target patterns with:
  - `rg -n "if 0:|do_segments|min\(analysis\.roi_ids\)|ROI_ID|edge_flag|band_concentration|plot_hr_segment_series|estimate_heart_rate_segment_series" /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate`
- Findings and actions:
  - Replaced runner `if 0:` segment block with `if cfg.do_segments`.
  - Removed implicit `min(analysis.roi_ids)` selection in runner and replaced with explicit `ROI_ID` validation.
  - Added QC metrics and segment series wiring where required.
  - Did not modify ticket markdown files or prior report files except creating this report.

## 6) Validation (commands actually run)
- `python3 -m py_compile /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate/heart_rate_analysis.py /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate/heart_rate_pipeline.py /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate/heart_rate_plots.py /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate/run_heart_rate_examples_fixed2.py /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate/tests/test_heart_rate_pipeline.py`
- `cd /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate && uv run pytest -q`
  - First run: 1 failing test (edge test with `use_abs=True` harmonic doubling)
  - Second run after test fix: pass
- `cd /Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/heart_rate_analysis/heart_rate && MPLBACKEND=Agg uv run python run_heart_rate_examples_fixed2.py`
  - Pass (non-interactive backend warning expected)

## 7) Expected validation markers
- `uv run pytest -q`:
  - `8 passed`
- Runner (`MPLBACKEND=Agg uv run python run_heart_rate_examples_fixed2.py`):
  - Prints `selected roi_id: 1`
  - Prints both method lines with QC fields:
    - `edge=<bool>`
    - `bc=<value>`
  - Prints `Agreement: Δbpm=..., ΔHz=...` when both present
  - Segment analysis/segment plot outputs appear only when `cfg.do_segments=True`

## 8) Summary of changes
- Added QC metrics (`edge_flag`, `edge_hz_distance`, `band_concentration`) to core estimates and debug payloads.
- Added QC metric computation helper using configurable edge margin and peak-neighborhood concentration.
- Added segment-window series estimator (`estimate_heart_rate_segment_series`) with config controls.
- Extended per-ROI pipeline config with QC/segment controls and persisted them in summary dict output.
- Added optional per-ROI segment payload caching in `HeartRatePerRoiResults`.
- Updated plotting config and plot functions to:
  - return `Axes`
  - keep `ax: Optional[plt.Axes] = None` compatibility
  - annotate Lomb/Welch plots with QC text
  - provide a segment series plotting helper.
- Updated runner to require explicit `ROI_ID` and validate it exists (no implicit smallest ROI).
- Re-enabled segment analysis path under `cfg.do_segments` and added optional segment QC plot.
- Added docs for QC metrics and segment interpretation.
- Added tests for QC summary keys, edge-flag behavior, and segment gating behavior.

## 9) Risks / tradeoffs
- Plot QC annotations re-run estimators internally for annotation text; this is simple and robust but duplicates compute.
- Segment series currently uses Welch windows for QC by default; Lomb windowed mode is available via function parameter but not surfaced in runner.
- Segment series stores `edge_flag` as numeric (`1/0/NaN`) in serialized payload for easy JSON plotting; callers should treat as indicator values.

## 10) Self-critique
### Pros
- Ticket goals are implemented end-to-end (QC metrics, edge handling, segment gating, explicit runner ROI selection, docs, tests).
- Diffs are focused on requested behavior and maintain existing runner primary `(3,1)` plot layout.
- Coverage increased with explicit tests for new QC/segment behavior.

### Cons
- Some legacy top-of-file runner narrative text remains historical and could be streamlined in a future cleanup ticket.
- QC annotation in plotting computes estimates again rather than consuming runner-provided estimates/debug payload.

### Drift risk
- Moderate: QC metrics are now in core and pipeline, but plotting annotations currently recompute and could diverge if future preprocessing defaults diverge.

### Red flags / architectural violations (if any)
- None identified relative to ticket_4_6 scope and `CODEX_RULES.md`.
