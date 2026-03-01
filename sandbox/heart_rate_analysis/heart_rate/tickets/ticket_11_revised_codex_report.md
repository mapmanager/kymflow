# Ticket 11 Revised Codex Report

## 1) Modified code files
- `heart_rate_pipeline.py`
- `heart_rate_batch.py`
- `tests/test_heart_rate_batch.py`

## 2) Artifacts created/updated
- `tickets/ticket_11_revised_codex_report.md`

## 3) Scope confirmation
- Confirmed: no files outside `kymflow/sandbox/heart_rate_analysis/heart_rate/` were modified.
- Confirmed: no files outside this ticket’s **Allowed edits** list were modified.

## 4) Unified diff (short)
Note: new files are shown as concise added hunks.

### `heart_rate_pipeline.py`
```diff
@@
+from dataclasses import dataclass, field, replace
+from datetime import datetime, timezone
+import json
@@
+RESULTS_JSON_SCHEMA_VERSION = 1
@@ class HRAnalysisConfig:
+@classmethod
+def from_dict(...)
@@ class HeartRateResults:
+@classmethod
+def from_dict(...)
@@ class HeartRatePerRoiResults:
+@classmethod
+def from_dict(...)
@@ class HeartRateAnalysis.__init__
-source: Optional[str] = None
+source_path: Optional[Path] = None
+source: Optional[str] = None
@@ class HeartRateAnalysis.from_csv
-return cls(..., source=str(csv_path))
+return cls(..., source_path=csv_path)
@@ class HeartRateAnalysis
+def default_results_json_path(...) -> Path
+def save_results_json(...) -> Path
+def load_results_json(...) -> None
@@ class HeartRateAnalysis.get_roi_summary
-inline summary-building logic
+return build_roi_summary_from_result(...)
@@
+def build_roi_summary_from_result(...)
```
Omitted hunks: unchanged estimator invocation code in `run_roi`, unchanged agreement/status classifier internals.

### `heart_rate_batch.py` (new)
```diff
+@dataclass(frozen=True)
+class HRBatchTask: ...
+
+@dataclass(frozen=True)
+class HeartRateFileResult: ...
+
+def compute_hr_for_df(...)
+def compute_hr_for_csv(...)
+def run_hr_batch(..., backend: Literal["process", "thread"] = "process")
+def batch_results_to_dataframe(..., minimal: Literal["mini", "full"] = "mini")
```

### `tests/test_heart_rate_batch.py` (new)
```diff
+def test_df_init_requires_roi_column()
+def test_results_json_round_trip(...)
+def test_batch_thread_backend_supports_df_tasks(...)
+def test_batch_process_backend_rejects_df_tasks()
```

## 5) Search confirmation
I searched for the required patterns and APIs (`source_path`, `save_results_json`, `load_results_json`, `run_hr_batch`, process backend df restrictions, mini summary helper usage) and changed only the in-scope files.

## 6) Validation (commands actually run)
- `python3 -m py_compile heart_rate_pipeline.py heart_rate_batch.py tests/test_heart_rate_batch.py`
- `uv run pytest -q`
- `/Users/cudmore/Sites/kymflow_outer/kymflow/.venv/bin/python -c "from heart_rate_batch import run_hr_batch, HRBatchTask; print('ok')"`

## 7) Expected validation markers
- `uv run pytest -q` passes (current: `21 passed, 1 warning`).
- Import marker command prints:
  - `ok`
- JSON round-trip test writes:
  - `<stem>_heart_rate.json` (example: `sample_heart_rate.json`).

## 8) Summary of changes
- Added DataFrame-first `HeartRateAnalysis` source path support via `source_path`.
- Added explicit JSON persistence API on `HeartRateAnalysis`:
  - default path naming
  - save
  - load with schema validation
- Added `from_dict` deserialization helpers for:
  - `HRAnalysisConfig`
  - `HeartRateResults`
  - `HeartRatePerRoiResults`
- Added reusable per-ROI summary builder function to avoid duplicated summary logic.
- Added new `heart_rate_batch.py` with:
  - task/result dataclasses
  - shared compute core for df/csv
  - thread/process backends
  - strict process-backend rejection of df tasks
  - batch result to DataFrame helper
- Added deterministic tests for required ticket behaviors.

## 9) Risks / tradeoffs
- Persistence schema version is fixed at `1`; future schema changes require migration handling.
- `load_results_json` validates loaded ROI ids against current dataframe ROI ids and raises on mismatch; this is strict by design.
- Process backend uses pickle-safe worker payloads; very large configs/task lists may have serialization overhead.

## 10) Self-critique
### Pros
- Ticket goals implemented with minimal surface-area changes.
- No runner-script edits were made.
- Batch code reuses one compute core (`compute_hr_for_df`) to avoid algorithm duplication.

### Cons
- No dedicated docs file was added because docs were not in the revised ticket’s allowed edit list.
- Persistence tests currently cover single-ROI round-trip; broader multi-ROI persistence cases are not yet explicit.

### Drift risk
- Low to moderate: persistence schema and `from_dict` expectations must stay aligned as payload fields evolve.

### Red flags / architectural violations (if any)
- None identified within the revised ticket scope.
