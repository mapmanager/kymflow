# Ticket 029 Codex Report

Final report path written:
`/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis/tickets/ticket_029_multi_roi_channel_csv_flat_columns_codex_report.md`

## A) Modified code files
- `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
- `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/docs/multi_run_serialization.md`
- `kymflow/sandbox/diameter-analysis/tickets/ticket_029_multi_roi_channel_csv_flat_columns_codex_report.md`

## C) Unified diff

### `kymflow/sandbox/diameter-analysis/diameter_analysis.py`
```diff
@@
+RUN_KEY_RE = re.compile(r"^roi(?P<roi>\d+)_ch(?P<ch>\d+)$")
+WIDE_COLUMN_RE = re.compile(r"^(?P<field>[a-z0-9_]+)_roi(?P<roi>\d+)_ch(?P<ch>\d+)$")
@@
 class DiameterResult:
+    roi_id: int
+    channel_id: int
@@
+    def __post_init__(self) -> None:
+        self.roi_id = int(self.roi_id)
+        self.channel_id = int(self.channel_id)
@@
+        for key in ("roi_id", "channel_id"):
+            if key not in row or row[key] == "":
+                raise ValueError(f"Missing required row key: {key}")
@@
+class DiameterAnalysisBundle:
+    runs: dict[tuple[int, int], list[DiameterResult]]
+    schema_version: int = BUNDLE_SCHEMA_VERSION
+
+    def to_dict(self) -> dict[str, Any]: ...
+    @classmethod
+    def from_dict(cls, payload: dict[str, Any]) -> "DiameterAnalysisBundle": ...
+
+def bundle_to_wide_csv_rows(...): ...
+def bundle_from_wide_csv_rows(...): ...
@@
         if cfg.diameter_method == DiameterMethod.GRADIENT_EDGES and (...):
             self._apply_motion_constraints(results=results, params=cfg)
+        for idx, result in enumerate(results):
+            if result.roi_id != int(roi_id) or result.channel_id != int(channel_id):
+                raise RuntimeError("Internal result id mismatch ...")
```

### `kymflow/sandbox/diameter-analysis/tests/test_multi_run_serialization.py`
```diff
@@
+def test_bundle_json_roundtrip_two_runs() -> None:
+    bundle = _make_bundle()
+    payload = bundle.to_dict()
+    loaded = DiameterAnalysisBundle.from_dict(json.loads(json.dumps(payload)))
+    _assert_bundle_equivalent(loaded, bundle)
+
+def test_bundle_from_dict_missing_roi_or_channel_fails_fast() -> None:
+    ...
+
+def test_wide_csv_roundtrip_and_column_naming() -> None:
+    header, rows = bundle_to_wide_csv_rows(bundle)
+    assert all("__" not in col for col in header)
+    assert all(re.search(r"_roi\d+_ch\d+$", c) for c in suffix_cols)
+    loaded = bundle_from_wide_csv_rows(header, rows)
+    _assert_bundle_equivalent(loaded, bundle)
+
+def test_analyze_strict_roi_channel_propagation() -> None:
+    ...
+    assert all(r.roi_id == 7 for r in results)
+    assert all(r.channel_id == 5 for r in results)
```

## D) Search confirmation
Searches performed:
- `rg -n "class DiameterRunKey|class DiameterAnalysisBundle|bundle_to_wide_csv_rows|bundle_from_wide_csv_rows|Internal result id mismatch|Missing required row key|WIDE_COLUMN_RE" diameter_analysis.py`
- `rg -n "test_bundle_json_roundtrip_two_runs|test_wide_csv_roundtrip_and_column_naming|test_analyze_strict_roi_channel_propagation" tests/test_multi_run_serialization.py`
- `rg -n "row.get(\"channel_id\"|roi_id: int \| None|channel_id: int \| None" --glob '!tickets/**'`

Outcome:
- Added new bundle/json/wide-csv serialization APIs.
- Confirmed no runtime `row.get("channel_id", ...)` fallback remains.
- Confirmed strict ROI/channel checks in result parsing and test coverage.

## E) Validation commands run
From `/Users/cudmore/Sites/kymflow_outer/kymflow/sandbox/diameter-analysis`:

1. `uv run pytest`
- First run: failed (2 tests in new suite due NaN equality in raw dict comparison).
- Fix applied: NaN-safe equivalence helper in tests.
- Second run: passed.
- Final status: `75 passed, 1 warning`.

## F) Summary of changes
- Added `DiameterRunKey` and `DiameterAnalysisBundle` multi-run container with strict `to_dict()`/`from_dict()`.
- Added wide CSV conversion helpers:
  - `bundle_to_wide_csv_rows(...)`
  - `bundle_from_wide_csv_rows(...)`
- Enforced strict required `roi_id` / `channel_id` in `DiameterResult.from_row(...)`.
- Added strict runtime validation in `analyze(...)` that every produced result carries the exact passed ROI/channel IDs.
- Added docs for bundle JSON schema + wide CSV naming + fail-fast policy.
- Added dedicated tests for JSON roundtrip, wide CSV roundtrip, naming convention, missing-key failures, and strict analyze propagation.

## G) Risks / tradeoffs
- Wide CSV roundtrip preserves frame metrics represented by `DiameterResult`; any future added result fields require updating wide-field maps.
- `include_time=False` in wide export removes `center_row`, and current parser requires `center_row` for reconstruction.
- JSON roundtrip tests require NaN-safe equivalence because some float fields can legitimately be `NaN`.

## H) Self-critique
- Pros:
  - Ticket requirements for strictness, multi-run schema, naming convention, and tests are covered.
  - Parsing paths are fail-fast and explicit, avoiding silent fallback behavior.
- Cons:
  - Wide CSV parser/exporter currently focuses on `DiameterResult` fields and does not embed extra run metadata beyond `(roi_id, channel_id)`.
- Drift risk:
  - If result schema evolves, wide CSV field lists must be updated in lockstep.
- What I would do differently next:
  - Add a compact versioned field registry for wide CSV to reduce maintenance overhead when `DiameterResult` evolves.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
