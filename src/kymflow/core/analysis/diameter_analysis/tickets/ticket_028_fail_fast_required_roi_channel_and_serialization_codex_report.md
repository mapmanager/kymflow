# Ticket 028 Codex Report

Final report path written:
`/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis/tickets/ticket_028_fail_fast_required_roi_channel_and_serialization_codex_report.md`

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/tests/test_results_aligned_schema.py`
- `kymflow/sandbox/diameter-analysis/tests/test_required_roi_channel_analyze_v2.py`

## B) Artifacts created
- Report file:
  - `/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis/tickets/ticket_028_fail_fast_required_roi_channel_and_serialization_codex_report.md`

## C) Unified diff

### `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
```diff
@@
-class DiameterResult:
-    roi_id: int | None
-    channel_id: int | None
+class DiameterResult:
+    roi_id: int
+    channel_id: int
@@
+    def __post_init__(self) -> None:
+        self.roi_id = int(self.roi_id)
+        self.channel_id = int(self.channel_id)
@@
-        payload = {
-            "roi_id": int(row["roi_id"]),
-            "channel_id": int(row.get("channel_id", "1")),
+        for key in ("roi_id", "channel_id"):
+            if key not in row or row[key] == "":
+                raise ValueError(f"Missing required row key: {key}")
+        payload = {
+            "roi_id": int(row["roi_id"]),
+            "channel_id": int(row["channel_id"]),
@@
-        if backend == "serial":
-            results = [self._analyze_center(i, cfg, t0, t1, x0, x1) for i in centers]
+        if backend == "serial":
+            results = [
+                self._analyze_center(i, cfg, t0, t1, x0, x1, roi_id=roi_id, channel_id=channel_id)
+                for i in centers
+            ]
@@
-    def _resolve_roi(self, roi: tuple[int, int, int, int] | None) -> tuple[int, int, int, int]:
-        n_time, n_space = self.kymograph.shape
-        if roi is None:
-            return 0, n_time, 0, n_space
+    def _resolve_roi(self, roi: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
+        n_time, n_space = self.kymograph.shape
@@
-                            channel_id=(
-                                int(result.channel_id)
-                                if getattr(result, "channel_id", None) is not None
-                                else 1
-                            ),
+                            channel_id=int(result.channel_id),
```

### `kymflow/sandbox/diameter-analysis/tests/test_results_aligned_schema.py`
```diff
@@
-            roi_id=None,
-            channel_id=None,
+            roi_id=1,
+            channel_id=1,
```

### `kymflow/sandbox/diameter-analysis/tests/test_required_roi_channel_analyze_v2.py`
```diff
@@
+from diameter_analysis import DiameterAnalyzer, DiameterDetectionParams, DiameterResult
@@
+def test_diameter_result_requires_roi_and_channel_at_construction() -> None:
+    with pytest.raises(TypeError):
+        DiameterResult(...)
+
+def test_from_row_raises_when_roi_or_channel_missing() -> None:
+    ...
+    with pytest.raises(ValueError, match="Missing required row key: roi_id"):
+        DiameterResult.from_row(missing_roi)
+    with pytest.raises(ValueError, match="Missing required row key: channel_id"):
+        DiameterResult.from_row(missing_channel)
```

## D) Search confirmation
Searches run:
- `rg -n "roi_id: int \| None|channel_id: int \| None|row\.get\(\"channel_id\"" kymflow/sandbox/diameter-analysis --glob '!tickets/**'`
- `rg -n "_resolve_roi\(" kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `rg -n "DiameterResult\(" kymflow/sandbox/diameter-analysis --glob '!tickets/**'`

Outcome:
- Removed Optional typing for `DiameterResult.roi_id/channel_id` in runtime code.
- Removed `channel_id` defaulting in row deserialization.
- `_resolve_roi` remains explicit-only (no `None` path).
- Updated `DiameterResult` construction sites to always pass explicit ROI/channel.

## E) Validation commands run
Executed from `/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis`:

1. `uv run pytest`
- Result: PASS (`71 passed, 1 warning`).

## F) Summary of changes
- Tightened `DiameterResult` schema to require `roi_id` and `channel_id` as non-optional ints.
- Enforced fail-fast CSV deserialization for missing `roi_id`/`channel_id`.
- Ensured per-frame results are constructed with explicit ROI/channel IDs (no post-hoc patching from `None`).
- Removed serialization fallback-to-1 behavior for `channel_id`.
- Added tests asserting fail-fast behavior for missing ROI/channel keys and required result construction.

## Assumptions made
- Keeping `roi_bounds` off `DiameterResult` is acceptable because the ticket marks that field as optional/recommended, not mandatory.
- Existing GUI/controller explicit defaults (`roi_id=1`, `channel_id=1`) at app layer remain valid and are outside analyzer/serialization defaulting.

## G) Risks / tradeoffs
- Stricter deserialization can reject older CSV artifacts missing `channel_id`; this is intentional fail-fast behavior per ticket.
- `DiameterAlignedResults` ROI/channel are now strict ints; synthetic paths must always provide explicit IDs (tests updated accordingly).

## H) Self-critique
- Pros:
  - Implemented strict fail-fast semantics exactly where silent defaults existed.
  - Added targeted tests to lock schema behavior.
- Cons:
  - Compatibility with legacy artifacts is intentionally reduced.
- Drift risk:
  - Any external script creating partial rows without `channel_id` will now fail immediately.
- If iterating further:
  - Add an explicit migration utility for legacy CSVs rather than silent in-code fallback.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
