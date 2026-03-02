# ticket_003_gradient_edges_codex_report

Final report path written:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_003_gradient_edges_codex_report.md`

## Summary of what changed
- Added `GRADIENT_EDGES` diameter method with configurable Gaussian smoothing and central-difference derivative edge detection.
- Extended params/result schema for gradient settings and edge-strength QC metrics.
- Updated plotting to display transposed kymographs (`transpose()`) with x=time and y=space, using physical units when available.
- Added new tests for gradient behavior, accuracy, serial/thread equality, and transpose-plot shape sanity.
- Updated example script to run both `THRESHOLD_WIDTH` and `GRADIENT_EDGES` with transpose-aware plotting.

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/diameter_plots.py`
- `kymflow/sandbox/diameter-analysis/run_example.py`
- `kymflow/sandbox/diameter-analysis/tests/test_ticket_003_gradient_edges.py`

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/tickets/ticket_003_gradient_edges_codex_report.md`
- `kymflow/sandbox/diameter-analysis/tests/test_ticket_003_gradient_edges.py`

## File-by-file list of changes
- `diameter_analysis.py`
  - Added `DiameterMethod.GRADIENT_EDGES`.
  - Extended `DiameterDetectionParams` with `gradient_sigma`, `gradient_kernel`, `gradient_min_edge_strength`.
  - Extended `DiameterResult` with `edge_strength_left/right` and persisted these in CSV.
  - Added `_gradient_edges()` implementation: smooth profile, central-diff derivative, max/min gradient edges, invalid-order handling.
  - Added gradient-aware QC flags (`gradient_invalid_order`, `gradient_low_edge_strength`) and qc score weighting.
  - `analyze()` now dispatches to one method per run based on `params.diameter_method`.
- `diameter_plots.py`
  - Added transpose-aware image display (`img_disp = kymograph.transpose()`).
  - Updated axis conventions and labels: x=time, y=space with unit fallback logic.
  - Updated overlays to plot each result at time on x and edge position on y in the same transposed coordinate system.
  - Updated plotly dict heatmap `z` to transposed image shape `(space, time)`.
- `run_example.py`
  - Added quick switching (loop) between `THRESHOLD_WIDTH` and `GRADIENT_EDGES`.
  - Produces stacked 2x1 matplotlib plots and plotly dict summaries for each method.
- `tests/test_ticket_003_gradient_edges.py`
  - Added end-to-end gradient tests, accuracy tolerance checks against synthetic truth, serial vs threads parity, and transpose-plot shape checks.

## C) Unified diff (short)
### `sandbox/diameter-analysis/diameter_analysis.py`
```diff
@@
 class DiameterMethod(str, Enum):
     THRESHOLD_WIDTH = "threshold_width"
+    GRADIENT_EDGES = "gradient_edges"
@@
+    gradient_sigma: float = 1.5
+    gradient_kernel: str = "central_diff"
+    gradient_min_edge_strength: float = 0.02
@@
+    def _gradient_edges(...):
+        ...
+        left_idx = int(np.argmax(deriv))
+        right_idx = int(np.argmin(deriv))
+        if left_idx >= right_idx:
+            flags.append("gradient_invalid_order")
```

### `sandbox/diameter-analysis/diameter_plots.py`
```diff
@@
+def _display_axes(...):
+    img_disp = arr.transpose()
+    ...
@@
-    ax.imshow(kymograph, aspect="auto", origin="lower", cmap="gray")
-    ax.plot(left, y, ...)
-    ax.plot(right, y, ...)
+    ax.imshow(img_disp, ..., extent=extent)
+    ax.plot(x_time, left_space, ...)
+    ax.plot(x_time, right_space, ...)
```

### `sandbox/diameter-analysis/run_example.py`
```diff
@@
-from diameter_analysis import DiameterAnalyzer, DiameterDetectionParams
+from diameter_analysis import DiameterAnalyzer, DiameterDetectionParams, DiameterMethod
@@
-    params = DiameterDetectionParams(...)
-    results = analyzer.analyze(params=params, backend="threads")
+    for method in (DiameterMethod.THRESHOLD_WIDTH, DiameterMethod.GRADIENT_EDGES):
+        _run_one_method(analyzer, payload, method)
```

### `sandbox/diameter-analysis/tests/test_ticket_003_gradient_edges.py`
```diff
+def test_gradient_edges_runs_and_is_mostly_ordered() -> None:
+    ...
+
+def test_gradient_edges_serial_threads_identical() -> None:
+    ...
+
+def test_plot_orientation_uses_transposed_shape() -> None:
+    ...
```

## D) Search confirmation
Searched for new method/flags and transpose requirement with:
- `GRADIENT_EDGES|gradient_sigma|transpose\(\)|gradient_invalid_order|gradient_low_edge_strength`

Result:
- New method and flags are implemented in analysis and tests.
- Plotting uses explicit `transpose()` in `diameter_plots.py`.
- No duplicate gradient implementation path found outside intended analysis engine.

## E) Validation commands run
Executed from `kymflow/sandbox/diameter-analysis/` exactly as ticket requires:

1. `uv run pytest -q`
- Result: pass
- Output: `12 passed, 1 warning in 0.71s`

2. `uv run python run_example.py`
- Result: pass
- Output summary includes both methods:
  - `method: threshold_width`
  - `method: gradient_edges`
  - each with result count and plotly dict summary

## Assumptions made
- User request "process ticket 003" mapped to existing file `ticket_003_gradient_edges.md` because `ticket_003.md` was not present.

## F) Summary of changes
- Added gradient-edge method and params.
- Added edge-strength QC fields/flags.
- Switched image plotting conventions to transposed time-vs-space coordinates.
- Added ticket-003 test coverage and updated example script for method switching.

## G) Risks / tradeoffs
- Gradient edge detection is pixel-level (no subpixel interpolation yet).
- Low-edge-strength thresholds are heuristic and may need dataset-specific tuning.
- SciPy is optional; fallback Gaussian smoothing is implemented for environments without SciPy.

## H) Self-critique
- Pros: satisfies method expansion, plotting orientation requirements, and acceptance tests.
- Cons: QC scoring remains heuristic and may under/over-penalize in edge cases.
- Drift risk: moderate if future tickets revise persistence schema or scoring formulas.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
