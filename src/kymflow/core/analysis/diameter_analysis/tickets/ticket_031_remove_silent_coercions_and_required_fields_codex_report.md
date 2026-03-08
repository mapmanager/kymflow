# Ticket 031 Codex Report

Final report path written:
`/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis/tickets/ticket_031_remove_silent_coercions_and_required_fields_codex_report.md`

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/tests/test_required_roi_channel_analyze_v2.py`
- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`

## B) Artifacts created
- Report:
  - `/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis/tickets/ticket_031_remove_silent_coercions_and_required_fields_codex_report.md`

## C) Unified diff (short)

### `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
```diff
@@
+def _require_int(value: Any, *, field_name: str) -> int:
+    if isinstance(value, bool) or not isinstance(value, int):
+        raise ValueError(f"{field_name} must be int, got {type(value).__name__}")
+    return value
@@
 class DiameterResult:
@@
-    def __post_init__(self) -> None:
-        self.roi_id = int(self.roi_id)
-        self.channel_id = int(self.channel_id)
+    def __post_init__(self) -> None:
+        _require_int(self.roi_id, field_name="roi_id")
+        _require_int(self.channel_id, field_name="channel_id")
@@
 class DiameterAnalysisBundle:
@@
-            roi_id, channel_id = int(key[0]), int(key[1])
+            roi_id = _require_int(key[0], field_name=f"run key roi_id for {key!r}")
+            channel_id = _require_int(key[1], field_name=f"run key channel_id for {key!r}")
@@
-            if int(run_payload["roi_id"]) != roi_id or int(run_payload["channel_id"]) != channel_id:
+            run_roi_id = _require_int(run_payload["roi_id"], field_name=f"Run {run_name!r} roi_id")
+            run_channel_id = _require_int(run_payload["channel_id"], field_name=f"Run {run_name!r} channel_id")
+            if run_roi_id != roi_id or run_channel_id != channel_id:
@@
 def bundle_to_wide_csv_rows(..., include_time: bool = True, ...):
+    if not include_time:
+        raise ValueError("bundle_to_wide_csv_rows requires include_time=True")
-    if not include_time and "center_row" in fields:
-        fields.remove("center_row")
```

### `kymflow/sandbox/diameter-analysis/tests/test_required_roi_channel_analyze_v2.py`
```diff
@@
+def test_diameter_result_rejects_non_int_roi_or_channel() -> None:
+    with pytest.raises(ValueError, match="roi_id must be int"):
+        DiameterResult(roi_id="1", channel_id=1, ...)
+    with pytest.raises(ValueError, match="channel_id must be int"):
+        DiameterResult(roi_id=1, channel_id="1", ...)
```

### `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
```diff
@@
+def test_bundle_from_dict_rejects_non_int_run_ids() -> None:
+    payload["runs"]["roi1_ch1"]["roi_id"] = "1"
+    with pytest.raises(ValueError, match="roi_id"):
+        DiameterAnalysisBundle.from_dict(payload)
+
+def test_wide_csv_export_requires_include_time_true() -> None:
+    with pytest.raises(ValueError, match="include_time=True"):
+        bundle_to_wide_csv_rows(bundle, include_time=False)
```

## D) Search confirmation
Searches run:
- `rg -n "_require_int|include_time=True|test_wide_csv_export_requires_include_time_true|test_diameter_result_rejects_non_int_roi_or_channel|test_bundle_from_dict_rejects_non_int_run_ids" kymflow/sandbox/diameter-analysis --glob '!tickets/**'`

Outcome:
- Added strict integer validation for required IDs (no silent coercion).
- Wide CSV export now fails fast when asked to omit required time/index support.
- Added tests for missing/invalid required field failure modes.

## E) Validation commands run
From `/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis`:

1. `uv run pytest`
- Result: PASS (`81 passed, 1 warning`).

## F) Summary of changes
- Removed silent ID coercion in `DiameterResult` by replacing `int(...)` patching with explicit validation.
- Tightened bundle ID handling to reject non-`int` run keys and payload IDs.
- Disallowed wide CSV export mode that can produce non-reconstructable output (`include_time=False`).
- Added tests for invalid required-ID types and wide CSV required-field contract.

## G) Risks / tradeoffs
- Stricter ID validation may reject previously tolerated non-int payloads (`"1"` strings in JSON run metadata).
- `include_time=False` now hard-fails to guarantee reconstructable wide CSV schema.

## H) Self-critique
- Pros:
  - Changes are minimal and directly targeted at silent coercion removal.
  - Tests cover both required-ID tightening and wide CSV required-field behavior.
- Cons:
  - Strict type checks rely on Python `int` runtime type; external JSON producers must match schema exactly.
- Drift risk:
  - If future schema intentionally allows string IDs, this strict policy must be updated with explicit ticket direction.
- What I would do differently next:
  - Add a dedicated schema document section for runtime type strictness of run IDs.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
