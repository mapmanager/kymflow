# ticket_022_results_refactor_aligned_arrays_and_serialization_schema_codex_report

## Final report path
- `kymflow/sandbox/diameter-analysis/tickets/ticket_022_results_refactor_aligned_arrays_and_serialization_schema_codex_report.md`

## Summary of changes
- Added a canonical aligned-array results dataclass (`DiameterAlignedResults`) with strict length validation, `None`-based missing-value normalization, QC aligned arrays, and `to_dict`/`from_dict` support.
- Added `DiameterAnalyzer.analyze_aligned(...)` so callers can request the canonical aligned schema directly.
- Refactored brittle `DiameterResult.to_row/from_row` logic to use shared dataclass conversion (`to_dict/from_dict`) plus a single `ROW_FIELDS` contract.
- Updated GUI controller/plotting to consume aligned arrays (`time_s`, `left_um`, `right_um`, `center_um`, `diameter_um`, `diameter_um_filtered`) while keeping backward compatibility for analyzer test doubles.
- Added pytest coverage for aligned schema validation, serialization roundtrip with `None`, QC alignment, and row roundtrip behavior.

## File-by-file changes
### Modified code files
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/gui/controllers.py`
- `kymflow/sandbox/diameter-analysis/gui/plotting.py`
- `kymflow/sandbox/diameter-analysis/serialization.py`
- `kymflow/sandbox/diameter-analysis/__init__.py`
- `kymflow/sandbox/diameter-analysis/tests/test_results_aligned_schema.py` (new)

### Artifacts created
- `kymflow/sandbox/diameter-analysis/tickets/ticket_022_results_refactor_aligned_arrays_and_serialization_schema_codex_report.md`

## Unified diffs (short)
### `diameter_analysis.py`
```diff
+ALIGNED_RESULTS_SCHEMA_VERSION = 1
+
+@dataclass(frozen=True)
+class DiameterAlignedResults:
+    """Aligned per-frame diameter outputs for one ROI/channel analysis."""
+    ...
+    def __post_init__(self) -> None:
+        # validates all aligned arrays have identical lengths
+        # normalizes NaN -> None on serialization surface
+
+    def to_dict(self) -> dict[str, Any]:
+        return dataclass_to_dict(self)
+
+    @classmethod
+    def from_dict(cls, payload: dict[str, Any]) -> "DiameterAlignedResults":
+        return dataclass_from_dict(cls, payload)
+
+    @classmethod
+    def from_frame_results(...):
+        # converts list[DiameterResult] into aligned micron/QC arrays
+
 class DiameterResult:
+    ROW_FIELDS: ClassVar[tuple[str, ...]] = (...)
+    def to_dict(self) -> dict[str, Any]: ...
+    @classmethod
+    def from_dict(cls, payload: dict[str, Any]) -> "DiameterResult": ...
     def to_row(...):
-        # manual mapping
+        base = self.to_dict()
+        # shared mapping from base
     @classmethod
     def from_row(...):
-        # manual constructor
+        payload = {...}
+        return cls.from_dict(payload)
+
+def analyze_aligned(...)-> DiameterAlignedResults:
+    frame_results = self.analyze(...)
+    return DiameterAlignedResults.from_frame_results(...)
```

### `gui/controllers.py`
```diff
-            res = analyzer.analyze(params=self.state.detection_params)
-            self.state.results = res
+            source = "synthetic" if self.state.source == "synthetic" else "real"
+            roi_id = DEFAULT_ROI_ID if source == "real" else None
+            channel_id = DEFAULT_CHANNEL_ID if source == "real" else None
+            if hasattr(analyzer, "analyze_aligned"):
+                self.state.results = analyzer.analyze_aligned(...)
+            else:
+                frame_results = analyzer.analyze(...)
+                self.state.results = DiameterAlignedResults.from_frame_results(...)
```
```diff
+        if hasattr(res, "left_um") and hasattr(res, "right_um") and hasattr(res, "center_um"):
+            # consume aligned arrays directly for overlay traces
+            if getattr(res, "time_s", None) is not None:
+                seconds = np.asarray([float(v) for v in res.time_s], dtype=float)
+            return seconds, left, right, center
```

### `gui/plotting.py`
```diff
+def _extract_time_s(results: Any, seconds_per_line: float, n_points: int) -> np.ndarray: ...
+def _extract_filtered_diameter_um(results: Any) -> Optional[np.ndarray]: ...
+
 def _extract_diameter_um(results: Any, um_per_pixel: float) -> Optional[np.ndarray]:
+    if hasattr(results, "diameter_um"):
+        return np.asarray([...], dtype=float)
 
-    t = _time_axis(len(d_um), seconds_per_line=float(seconds_per_line))
+    t = _extract_time_s(results, seconds_per_line=float(seconds_per_line), n_points=len(d_um))
 
-    d_f = apply_post_filter_1d(d_um, post_filter_params)
+    d_f = _extract_filtered_diameter_um(results)
+    if d_f is None:
+        d_f = apply_post_filter_1d(d_um, post_filter_params)
```

### `serialization.py`
```diff
 def dataclass_to_dict(obj: Any) -> dict[str, Any]:
+    """Convert a dataclass instance into JSON-safe nested dictionaries/lists."""
 
 def dataclass_from_dict(cls: type[Any], payload: dict[str, Any]) -> Any:
+    """Instantiate a dataclass from a dictionary payload."""
```

### `__init__.py`
```diff
 from diameter_analysis import (
+    ALIGNED_RESULTS_SCHEMA_VERSION,
+    DiameterAlignedResults,
     ...
 )
 __all__ = [
+    "ALIGNED_RESULTS_SCHEMA_VERSION",
+    "DiameterAlignedResults",
     ...
 ]
```

### `tests/test_results_aligned_schema.py`
```diff
+def test_aligned_results_length_mismatch_raises() -> None: ...
+def test_aligned_results_roundtrip_preserves_none() -> None: ...
+def test_qc_flags_aligned_with_trace_length() -> None: ...
+def test_diameter_result_row_roundtrip() -> None: ...
```

## Search confirmation
- Searched patterns:
  - `to_row(` / `from_row(` / `DiameterResult`
  - `state.results` / `make_diameter_figure_dict(`
  - `left_edge_px` / `right_edge_px`
- Outcome:
  - Updated all active GUI/controller plotting consumption points in `gui/controllers.py` and `gui/plotting.py` to support canonical aligned arrays first.
  - Kept legacy fallbacks (DataFrame/list/object) in place for compatibility.
  - Refactored `DiameterResult.to_row/from_row` in `diameter_analysis.py`; no other row-mapping implementations remained in scope.

## Validation commands run
Ran from `kymflow/sandbox/diameter-analysis/`.

1. `uv run pytest`
- First run: **failed** with 2 tests in `tests/test_units_resolution.py` because fake analyzer stubs only implemented `analyze()` and not new `analyze_aligned()`.
- Fix applied: controller fallback path wraps `analyze()` output via `DiameterAlignedResults.from_frame_results(...)`.

2. `uv run pytest`
- Second run: **passed**.
- Result: `51 passed, 1 warning`.

## Assumptions made
- `source="real"` is used for non-synthetic data in the aligned schema (including kymflow-backed loading).
- Existing per-frame field `qc_edge_violation` does not split left/right edges; therefore both `qc_left_edge_violation` and `qc_right_edge_violation` are mapped from that boolean for now.
- Controller should store canonical aligned schema in `state.results`; compatibility paths remain for tests and older consumers.

## Risks / limitations / next steps
- Left/right edge QC is currently symmetric because upstream analysis exposes one combined edge flag.
- CSV persistence remains row-based for `save_analysis/load_analysis`; this ticket did not replace disk I/O with aligned JSON persistence.
- Existing fallback branches for DataFrame/list/object in plotting remain to avoid regressions; long-term cleanup can remove them once all producers emit aligned schema.

## Self-critique
- Pros:
  - Introduces a single canonical results object with explicit validation and serialization safety.
  - Minimal GUI wiring changes while preserving backward compatibility.
  - Added focused tests exactly around alignment/serialization/QC contract.
- Cons:
  - Dual model exists (`DiameterResult` and `DiameterAlignedResults`) until save/load pipeline is migrated.
  - QC left/right detail is not truly independent yet.
- Drift risk / red flags:
  - If new QC fields are added to `DiameterResult`, conversion in `from_frame_results()` must be updated.
  - Future schema changes require explicit `schema_version` evolution logic.
- What I would do next:
  - Migrate persisted results to aligned schema payloads and add explicit versioned loader/upgrader.

## Required confirmation
No files outside `kymflow/sandbox/diameter-analysis/` were modified.
