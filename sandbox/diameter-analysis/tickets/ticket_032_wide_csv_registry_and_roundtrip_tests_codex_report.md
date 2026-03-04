# Ticket 032 Codex Report

Final report path written:
`/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis/tickets/ticket_032_wide_csv_registry_and_roundtrip_tests_codex_report.md`

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`

## B) Artifacts created
- Report:
  - `/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis/tickets/ticket_032_wide_csv_registry_and_roundtrip_tests_codex_report.md`
- Docs updated:
  - `kymflow/sandbox/diameter-analysis/docs/multi_run_serialization.md`

## C) Unified diff (short)

### `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
```diff
@@
+WIDE_CSV_TIME_COLUMNS: tuple[str, ...] = ("time_s",)
+WIDE_CSV_ARRAY_FIELDS: tuple[str, ...] = (...)
+WIDE_CSV_SCALAR_FIELDS: tuple[str, ...] = ()
@@
-WIDE_REQUIRED_RECON_FIELDS = ("center_row", ...)
+WIDE_REQUIRED_RECON_FIELDS = ("left_edge_px", "right_edge_px", "diameter_px", "peak", "baseline", "qc_score")
@@
-    fields = list(WIDE_BASE_FIELDS)
+    fields = list(WIDE_CSV_ARRAY_FIELDS)
@@
-    header = ["time_s"]
+    header = list(WIDE_CSV_TIME_COLUMNS)
@@
-    if "time_s" not in header:
-        raise ValueError("Wide CSV missing required column: time_s")
+    for col in WIDE_CSV_TIME_COLUMNS:
+        if col not in header:
+            raise ValueError(f"Wide CSV missing required time column: {col}")
@@
-        run_columns.setdefault(run_key, {})[match.group("field")] = col_idx
+        field_name = match.group("field")
+        if field_name not in WIDE_CSV_ARRAY_FIELDS:
+            raise ValueError(f"Unregistered wide CSV field: {field_name!r}")
+        run_columns.setdefault(run_key, {})[field_name] = col_idx
@@
-            center_raw = row[field_map["center_row"]]
-            if center_raw == "":
+            has_any_data = any(row[idx] != "" for field, idx in field_map.items() if field != "qc_flags")
+            if not has_any_data:
                 continue
@@
-                    center_row=_int_cell(row, field_map["center_row"]),
+                    center_row=row_idx,
```

### `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
```diff
@@
+from diameter_analysis import (..., WIDE_CSV_ARRAY_FIELDS, WIDE_CSV_SCALAR_FIELDS, WIDE_CSV_TIME_COLUMNS)
@@
+def test_wide_csv_registry_drives_header_fields() -> None:
+    ...
+
+def test_wide_csv_loader_fails_when_time_column_missing() -> None:
+    ...
+
+def test_wide_csv_loader_fails_when_required_run_field_missing() -> None:
+    ...
```

### `kymflow/sandbox/diameter-analysis/docs/multi_run_serialization.md`
```diff
@@
+Wide CSV export/import is registry-driven in `diameter_analysis.py`:
+- `WIDE_CSV_TIME_COLUMNS`
+- `WIDE_CSV_ARRAY_FIELDS`
+- `WIDE_CSV_SCALAR_FIELDS`
@@
+Wide CSV load is aligned by `time_s` and registered run fields; it does not depend on `center_row` ordering.
```

## D) Search confirmation
Searches run:
- `rg -n "WIDE_CSV_TIME_COLUMNS|WIDE_CSV_ARRAY_FIELDS|WIDE_CSV_SCALAR_FIELDS|required time column|test_wide_csv_loader_fails_when_time_column_missing|test_wide_csv_loader_fails_when_required_run_field_missing|test_wide_csv_registry_drives_header_fields" kymflow/sandbox/diameter-analysis --glob '!tickets/**'`

Outcome:
- Wide CSV export/import now uses canonical registries.
- Loader fails fast for missing required time column and missing required run-field columns.
- Loader no longer depends on `center_row` column for reconstruction alignment.

## E) Validation commands run
From `/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis`:

1. `uv run pytest`
- Initial run failed while refactoring (`time_s` incorrectly required as run-suffixed field; then center_row comparison mismatch in test).
- Fixed loader required-field set and row-presence logic; adjusted test equivalence to compare arrays/time/ids rather than center-row incidental indexing.
- Final result: PASS (`84 passed, 1 warning`).

## F) Summary of changes
- Added canonical wide CSV registries (`WIDE_CSV_TIME_COLUMNS`, `WIDE_CSV_ARRAY_FIELDS`, `WIDE_CSV_SCALAR_FIELDS`).
- Refactored wide CSV export/import to be registry-driven.
- Enforced required `time_s` presence via canonical time-column registry.
- Made loader drift-safe: reconstructs by registered fields and global `time_s`, without relying on center-row ordering.
- Added roundtrip and fail-fast tests for single/multi-run bundles and missing required columns.
- Updated multi-run serialization docs for registry and drift-safe loading contract.

## G) Risks / tradeoffs
- `center_row` is no longer persisted/reconstructed as a wide-field; reconstructed `center_row` uses row index and is incidental.
- Any future added per-time metrics require explicit registration in `WIDE_CSV_ARRAY_FIELDS` to participate in CSV roundtrip.

## H) Self-critique
- Pros:
  - Matches requested registry-driven, drift-safe, fail-fast serialization behavior.
  - Test suite now guards against missing time/field schema drift.
- Cons:
  - Existing helper/test equivalence needed explicit shift away from center-row identity.
- Drift risk:
  - Forgetting to update the registry when adding new result fields can omit columns silently from export (tests help, but field additions still need discipline).
- What I would do differently next:
  - Add one strict assertion test that all intended exported fields are declared in `WIDE_CSV_ARRAY_FIELDS` from a single documented list.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
