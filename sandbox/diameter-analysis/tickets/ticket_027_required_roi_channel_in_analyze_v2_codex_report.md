# Ticket 027 Codex Report

Final report path written:
`/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis/tickets/ticket_027_required_roi_channel_in_analyze_v2_codex_report.md`

## Summary of what changed
- Enforced `DiameterAnalyzer.analyze()` contract to require `roi_id`, `roi_bounds`, and `channel_id`.
- Removed ROI resolution-by-default behavior from analyzer path and required explicit ROI bounds.
- Ensured ROI/channel are captured in frame results and CSV serialization.
- Updated real-data GUI detect path to pass required ROI/channel and fail fast if missing.
- Updated example/tests to call new API.
- Added explicit tests for required args, invalid bounds, and ROI/channel serialization roundtrip.
- Updated detection-params docs to state ROI/channel contract.

## A) Modified code files
- `sandbox/diameter-analysis/diameter_analysis.py`
- `sandbox/diameter-analysis/gui/controllers.py`
- `sandbox/diameter-analysis/run_example.py`
- `sandbox/diameter-analysis/tests/test_analysis_hardened.py`
- `sandbox/diameter-analysis/tests/test_gradient_edges.py`
- `sandbox/diameter-analysis/tests/test_motion_constraints_qc.py`
- `sandbox/diameter-analysis/tests/test_post_filter_diameter.py`
- `sandbox/diameter-analysis/tests/test_results_aligned_schema.py`
- `sandbox/diameter-analysis/tests/test_scaffold.py`
- `sandbox/diameter-analysis/tests/test_synthetic_noise_models.py`
- `sandbox/diameter-analysis/tests/test_units_resolution.py`
- `sandbox/diameter-analysis/tests/test_required_roi_channel_analyze_v2.py` (new)

## B) Artifacts created
- Report:
  - `/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis/tickets/ticket_027_required_roi_channel_in_analyze_v2_codex_report.md`
- Non-code docs updated:
  - `sandbox/diameter-analysis/docs/detection_params.md`

## C) Unified diff (short per edited code file)

### `sandbox/diameter-analysis/diameter_analysis.py`
```diff
@@
 class DiameterResult:
+    roi_id: int | None
+    channel_id: int | None
@@
-    def to_row(self, *, roi_id: int, schema_version: int, um_per_pixel: float) -> dict[str, Any]:
+    def to_row(self, *, roi_id: int, channel_id: int, schema_version: int, um_per_pixel: float) -> dict[str, Any]:
@@
-            "roi_id": int(roi_id),
+            "roi_id": int(roi_id),
+            "channel_id": int(channel_id),
@@
-        payload = {
+        payload = {
+            "roi_id": int(row["roi_id"]),
+            "channel_id": int(row.get("channel_id", "1")),
@@
-    def analyze(self, params: Optional[DiameterDetectionParams] = None, *, backend: str = "serial", ...)
+    def analyze(self, params: Optional[DiameterDetectionParams] = None, *, roi_id: int, roi_bounds: tuple[int, int, int, int], channel_id: int, backend: str = "serial", ...)
@@
-        t0, t1, x0, x1 = self._resolve_roi(None)
+        t0, t1, x0, x1 = self._resolve_roi(roi_bounds)
@@
+        for r in results:
+            r.roi_id = int(roi_id)
+            r.channel_id = int(channel_id)
@@
-    def _resolve_roi(self, roi: tuple[int, int, int, int] | None) -> tuple[int, int, int, int]:
+    def _resolve_roi(self, roi: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
@@
-            "roi_id",
+            "roi_id",
+            "channel_id",
```

### `sandbox/diameter-analysis/gui/controllers.py`
```diff
@@
-            res = analyzer.analyze(params=self.state.detection_params)
+            roi_id = DEFAULT_ROI_ID
+            channel_id = DEFAULT_CHANNEL_ID
+            if self.state.source == "kymflow":
+                selected = self.state.selected_kym_image
+                if selected is None:
+                    raise RuntimeError("No selected kym image for real-data analysis.")
+                require_channel_and_roi(selected, channel=channel_id, roi_id=roi_id)
+                bounds = get_roi_pixel_bounds_for(selected, roi_id=roi_id)
+                roi_bounds = (int(bounds.row_start), int(bounds.row_stop), int(bounds.col_start), int(bounds.col_stop))
+            else:
+                n_time, n_space = self.state.img.shape
+                roi_bounds = (0, int(n_time), 0, int(n_space))
+
+            res = analyzer.analyze(
+                params=self.state.detection_params,
+                roi_id=roi_id,
+                roi_bounds=roi_bounds,
+                channel_id=channel_id,
+            )
```

### `sandbox/diameter-analysis/run_example.py`
```diff
@@
     results = analyzer.analyze(
         params=params,
+        roi_id=1,
+        roi_bounds=(0, int(payload["kymograph"].shape[0]), 0, int(payload["kymograph"].shape[1])),
+        channel_id=1,
         backend="threads",
         post_filter_params=post_filter_params,
     )
```

### `sandbox/diameter-analysis/tests/test_analysis_hardened.py`
```diff
@@
-    results = analyzer.analyze(params=params, backend="serial")
+    results = analyzer.analyze(
+        params=params,
+        roi_id=1,
+        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
+        channel_id=1,
+        backend="serial",
+    )
```

### `sandbox/diameter-analysis/tests/test_gradient_edges.py`
```diff
@@
-    serial = analyzer.analyze(params=params, backend="serial")
+    serial = analyzer.analyze(
+        params=params,
+        roi_id=1,
+        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
+        channel_id=1,
+        backend="serial",
+    )
```

### `sandbox/diameter-analysis/tests/test_motion_constraints_qc.py`
```diff
@@
-    results = analyzer.analyze(params=params)
+    results = analyzer.analyze(
+        params=params,
+        roi_id=1,
+        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
+        channel_id=1,
+    )
```

### `sandbox/diameter-analysis/tests/test_post_filter_diameter.py`
```diff
@@
-    results = analyzer.analyze(det, backend="serial", post_filter_params=pf)
+    results = analyzer.analyze(
+        det,
+        roi_id=1,
+        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
+        channel_id=1,
+        backend="serial",
+        post_filter_params=pf,
+    )
```

### `sandbox/diameter-analysis/tests/test_results_aligned_schema.py`
```diff
@@
-    aligned = analyzer.analyze_aligned(params=params, source="synthetic")
+    aligned = analyzer.analyze_aligned(
+        params=params,
+        roi_id=1,
+        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
+        channel_id=1,
+        source="synthetic",
+    )
@@
-    result = DiameterResult(
+    result = DiameterResult(
+        roi_id=1,
+        channel_id=1,
@@
-    row = result.to_row(roi_id=1, schema_version=1, um_per_pixel=0.4)
+    row = result.to_row(roi_id=1, channel_id=1, schema_version=1, um_per_pixel=0.4)
```

### `sandbox/diameter-analysis/tests/test_scaffold.py`
```diff
@@
-    results = analyzer.analyze(params=params, backend="serial")
+    results = analyzer.analyze(
+        params=params,
+        roi_id=1,
+        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
+        channel_id=1,
+        backend="serial",
+    )
```

### `sandbox/diameter-analysis/tests/test_synthetic_noise_models.py`
```diff
@@
-    results = analyzer.analyze(DiameterDetectionParams(stride=2), backend="serial")
+    results = analyzer.analyze(
+        DiameterDetectionParams(stride=2),
+        roi_id=1,
+        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
+        channel_id=1,
+        backend="serial",
+    )
```

### `sandbox/diameter-analysis/tests/test_units_resolution.py`
```diff
@@
-import numpy as np
+import numpy as np
+import pytest
@@
-        def analyze(self, params):
+        def analyze(self, params, **_kwargs):
             return []
@@
+def test_detect_kymflow_fails_fast_when_required_roi_or_channel_missing(monkeypatch) -> None:
+    ...
+    with pytest.raises(ValueError, match="Missing channel 1"):
+        controller.detect()
```

### `sandbox/diameter-analysis/tests/test_required_roi_channel_analyze_v2.py` (new)
```diff
@@ -0,0 +1,85 @@
+def test_analyze_requires_roi_and_channel_keyword_args() -> None:
+    ...
+
+def test_analyze_rejects_invalid_roi_bounds() -> None:
+    ...
+
+def test_save_load_roundtrip_preserves_roi_and_channel_ids(tmp_path) -> None:
+    ...
```

## D) Search confirmation
Searches executed and outcomes:
- `rg -n "params\.roi|cfg\.roi|\.roi\b" ... --glob '!tickets/**' --glob '!docs/**'`
  - Runtime code has no remaining `params.roi` / `cfg.roi` usage.
- `rg -n "\.analyze\(" sandbox/diameter-analysis --glob '!tickets/**'`
  - Updated all runtime/test callsites to pass required `roi_id`, `roi_bounds`, `channel_id`.
  - Remaining old-form example exists in `docs/usage.md`; not changed in this ticket because scope explicitly requested `docs/detection_params.md` update and runtime callsites/tests.

## E) Validation commands run
Executed from: `/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis`

1. `uv run pytest`
- First run: failed (1 test) in `tests/test_units_resolution.py::test_detect_kymflow_fails_fast_when_required_roi_or_channel_missing` because selected test object lacked valid units before reaching ROI/channel validation path.
- After fixing test setup: passed.
- Final result: `69 passed, 1 warning in 1.42s`.

2. `uv run python run_gui.py`
- Output confirmed startup: `NiceGUI ready to go on http://127.0.0.1:8001`
- Process was then interrupted intentionally (`Ctrl-C`) after confirming launch.

## F) Summary of changes
- API contract hardened: analysis now requires explicit ROI/channel selection.
- Serialization now includes `channel_id` (alongside `roi_id`) in rows and row parsing.
- GUI detect path now supplies ROI bounds from facade for real data and validates required ROI/channel on detect.
- Tests updated to new API; new dedicated test file added for required args, invalid bounds, and serialization propagation.
- Detection-params docs now explicitly define ROI/channel ownership at app/workflow level.

## Assumptions made
- For synthetic and generic non-kymflow sources, full-image ROI `(0, n_time, 0, n_space)` with `roi_id=1`, `channel_id=1` is acceptable.
- `run_gui.py` validation means successful startup/log-ready state, not a long interactive manual session.
- Existing schema version remains unchanged while adding `channel_id` support with backward-compatible `from_row` default.

## G) Risks / tradeoffs
- `docs/usage.md` still shows legacy `analyze(params=...)` example and is now stale relative to runtime API.
- `from_row` defaults missing `channel_id` to `1`; this is pragmatic for backward compatibility but may hide legacy data ambiguity.
- Real-data detect now validates ROI/channel both on load and detect; this is intentional fail-fast behavior but adds one additional guard call per detect.

## H) Self-critique
- Pros:
  - Ticket acceptance criteria are covered with explicit API, GUI, serialization, docs, and tests.
  - Added focused tests for the two highest-risk regressions (required args and ROI/channel persistence).
- Cons:
  - Report diffs for repetitive test callsite updates are abbreviated to keep readability.
  - Did not update `docs/usage.md` to avoid scope expansion beyond ticket-directed docs target.
- Drift risk/red flags:
  - Future callers outside this sandbox may still assume old `analyze()` signature.
  - If broader docs aren’t updated, users may follow stale examples.
- What I would do differently next:
  - Add a follow-up docs ticket to update `docs/usage.md` and any external snippets to the required ROI/channel signature.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
