# ticket_002_codex_report

## Summary of what changed
Implemented the hardened ticket_002 stepping engine and removed legacy placeholder analysis behavior from the active path. `DiameterAnalyzer.analyze(...)` now uses one stepping/binning engine for both `serial` and `threads` backends, adds threshold-width v1 detection with QC flags/scores, supports ROI + stride + odd windowing, and persists sidecars with schema versioning.

## Modified code files
- `__init__.py`
- `diameter_analysis.py`
- `diameter_plots.py`
- `synthetic_kymograph.py`
- `run_example.py`
- `tests/test_ticket_001_scaffold.py`
- `tests/test_ticket_002_hardened.py`

## Artifacts created
- `tickets/ticket_002_codex_report.md`
- `tests/test_ticket_002_hardened.py`

## File-by-file list of changes
- `diameter_analysis.py`
  - Added enums: `BinningMethod`, `Polarity`, `DiameterMethod`.
  - Expanded `DiameterDetectionParams` with required hardened fields and `to_dict()/from_dict()`.
  - Added `DiameterResult` dataclass (center/time/edges/diameter/peak-baseline/QC).
  - Implemented deterministic stepping engine with ROI `(t0,t1,x0,x1)` half-open convention, odd row-window binning, stride, polarity handling.
  - Implemented threshold-width v1 with missing-edge NaN behavior + QC flags.
  - Added provisional QC scoring in `[0,1]` (contrast, saturation, double-peak, missing edges).
  - Added threaded backend using chunking (`THREAD_CHUNK_SIZE`) and deterministic sorted merge.
  - Hardened persistence to:
    - `analysis_params.json` with `schema_version=1` and `rois` mapping.
    - `analysis_results.csv` with per-row `schema_version` and `roi_id`.
  - Added round-trip loader with schema validation.
- `diameter_plots.py`
  - Updated plotting functions to accept `list[DiameterResult]`.
  - Matplotlib and plotly-dict functions both render kymograph edge overlays and diameter-vs-time.
  - Added optional matplotlib `ax` argument for composable/staged layouts.
- `synthetic_kymograph.py`
  - Added deterministic synthetic generator exposing `truth` payload, including `truth_diameter_px` aligned to time rows.
- `run_example.py`
  - Runs threaded analyze with ROI/stride/window settings.
  - Produces stacked 2x1 matplotlib view (kymograph+edges, diameter vs time).
  - Produces plotly dicts for both views and prints short summaries.
- `tests/test_ticket_001_scaffold.py`
  - Updated to new engine return type and params schema while keeping scaffold sanity check.
- `tests/test_ticket_002_hardened.py`
  - Added acceptance-focused tests for stride semantics, serial/thread equality, persistence round-trip with schema, synthetic truth tolerance, and missing-edge QC behavior.
- `__init__.py`
  - Exported new enums/result/schema constants.

## Unified diff (short)
### `sandbox/diameter-analysis/__init__.py`
```diff
@@ -1,8 +1,21 @@
-from diameter_analysis import DiameterAnalyzer, DiameterDetectionParams
+from diameter_analysis import (
+    ANALYSIS_SCHEMA_VERSION,
+    BinningMethod,
+    DiameterAnalyzer,
+    DiameterDetectionParams,
+    DiameterMethod,
+    DiameterResult,
+    Polarity,
+)
```

### `sandbox/diameter-analysis/diameter_analysis.py`
```diff
@@ -1,9 +1,13 @@
+import csv
 import json
+import math
+from concurrent.futures import ThreadPoolExecutor
 from dataclasses import dataclass
+from enum import Enum
@@
+ANALYSIS_SCHEMA_VERSION = 1
+THREAD_CHUNK_SIZE = 512
@@
+class BinningMethod(str, Enum):
+    MEAN = "mean"
+    MEDIAN = "median"
```

### `sandbox/diameter-analysis/diameter_plots.py`
```diff
@@
-def plot_kymograph_with_edges_mpl(
-    kymograph: np.ndarray,
-    left_edge_px: Optional[np.ndarray] = None,
-    right_edge_px: Optional[np.ndarray] = None,
-):
+def plot_kymograph_with_edges_mpl(
+    kymograph: np.ndarray,
+    results: list[Any],
+    *,
+    ax: Optional[plt.Axes] = None,
+):
```

### `sandbox/diameter-analysis/synthetic_kymograph.py`
```diff
@@
 def generate_synthetic_kymograph(
@@
+    noise_sigma: float = 0.02,
 ) -> dict[str, Any]:
@@
+        "truth": {
+            "truth_diameter_px": diameter.copy(),
+            "truth_left_edge_px": left.copy(),
+            "truth_right_edge_px": right.copy(),
+        },
```

### `sandbox/diameter-analysis/run_example.py`
```diff
@@
-    params = DiameterDetectionParams(threshold_fraction=0.45, min_diameter_px=2.0)
-    analysis = analyzer.analyze(params=params)
+    params = DiameterDetectionParams(window_rows_odd=5, stride=2, roi=(0, 220, 0, 150))
+    results = analyzer.analyze(params=params, backend="threads")
@@
-    print(f"analysis keys: {sorted(analysis.keys())}")
+    print(f"results count: {len(results)}")
```

### `sandbox/diameter-analysis/tests/test_ticket_001_scaffold.py`
```diff
@@
-    params = DiameterDetectionParams(threshold_fraction=0.5, min_diameter_px=2.0)
+    params = DiameterDetectionParams(window_rows_odd=3, stride=2)
@@
-    result = analyzer.analyze(params=params)
-    assert set(result.keys()) == {
-        "time_s",
-        "diameter_px",
-        "diameter_um",
-        "left_edge_px",
-        "right_edge_px",
-    }
+    results = analyzer.analyze(params=params, backend="serial")
+    assert len(results) == 30
```

### `sandbox/diameter-analysis/tests/test_ticket_002_hardened.py`
```diff
+def test_stride_semantics_center_row_and_time() -> None:
+    ...
+
+def test_serial_and_threads_backends_match() -> None:
+    ...
+
+def test_save_load_roundtrip_schema_and_row_count(tmp_path: Path) -> None:
+    ...
+
+@pytest.mark.parametrize("mae_tol", [2.5, 3.5])
+def test_synthetic_truth_and_threshold_width_accuracy(mae_tol: float) -> None:
+    ...
```

## Search confirmation
Searched for legacy/duplicate placeholder paths and new API symbols:
- Pattern set: `threshold_fraction|min_diameter_px|placeholder|def analyze\(`
- Scope: `sandbox/diameter-analysis`
- Outcome: active code path uses only the new stepping engine in `diameter_analysis.py`. Remaining legacy mentions are in docs/tickets/reports, not executable analysis logic.

## Exact validation commands run + results
Executed from `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest -q`
- Result: pass
- Output: `7 passed, 1 warning in 0.29s`

2. `uv run python run_example.py`
- Result: pass
- Output:
  - `results count: 110`
  - `finite diameter points: 110`
  - `plotly kym dict keys: ['data', 'layout']`
  - `plotly diameter traces: 1`

## Assumptions made
- ROI convention is half-open `(t0,t1,x0,x1)` as allowed by ticket language.
- Threshold-width v1 edge detection uses threshold crossings on first/last above-threshold indices; boundary-touching cases are flagged and set to NaN.
- Provisional QC score uses simple weighted heuristic penalties and is explicitly non-final.

## Risks / limitations / what to do next
- Threshold-width v1 is intentionally simple; it may degrade for noisy/multimodal profiles.
- Crossing estimation currently uses index-level edges (no subpixel interpolation).
- QC heuristics are lightweight and may need domain-tuned thresholds.
- Next:
  - add subpixel crossing interpolation,
  - add stronger saturation heuristic tied to acquisition bit-depth,
  - add multi-ROI integration tests once ROI management expands.

## Self-critique
- Pros: ticket acceptance criteria are covered with deterministic serial/thread parity, schema-hard persistence, and robust no-crash behavior on missing edges.
- Cons: current edge locator is coarse and may over/under-estimate widths near clipping or low contrast.
- Drift risk: moderate for downstream tickets if schema fields expand without explicit version migration policy.

## ESCALATION
None.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
