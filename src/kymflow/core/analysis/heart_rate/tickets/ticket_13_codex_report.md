# Ticket 13 Codex Report

## 1) Modified code files
- `heart_rate_batch.py`
- `tests/test_heart_rate_batch_save.py`

## 2) Artifacts created/updated
- `tickets/ticket_13_codex_report.md`

## 3) Scope confirmation
- Confirmed: no files outside `kymflow/sandbox/heart_rate_analysis/heart_rate/` were modified.
- Confirmed: no files outside ticket 13 **Allowed edits** list were modified.

## 4) Unified diff (short)
### `heart_rate_batch.py`
```diff
@@
+import logging
+logger = logging.getLogger(__name__)
@@
+@dataclass(frozen=True)
+class HRBatchSaveResult:
+    csv_path: Path
+    ok: bool
+    saved_json_path: Optional[Path]
+    error: str = ""
@@
+def _run_and_save_one_csv(..., overwrite: bool) -> HRBatchSaveResult:
+    - HeartRateAnalysis.from_csv(csv_path)
+    - roi selection/validation
+    - cfg defaulting via HRAnalysisConfig()
+    - run analysis per ROI
+    - save to default_results_json_path()
+    - returns ok/error record; logs warning on exception
@@
+def _run_and_save_worker(payload: tuple[str, Optional[list[int]], Optional[dict], bool]) -> HRBatchSaveResult
@@
+def batch_run_and_save(
+    csv_paths: Sequence[Path],
+    *,
+    roi_ids: Optional[Sequence[int]] = None,
+    cfg: Optional[HRAnalysisConfig] = None,
+    overwrite: bool = True,
+    backend: Literal["process", "thread", "serial"] = "process",
+    n_workers: int = 0,
+) -> list[HRBatchSaveResult]:
+    - validates inputs/backend
+    - serial/thread/process implementations
+    - preserves input order
+    - per-file failures recorded (no raise)
```
Omitted hunks: pre-existing batch APIs (`run_hr_batch`, `batch_results_to_dataframe`) unchanged.

### `tests/test_heart_rate_batch_save.py`
```diff
+def test_batch_run_and_save_serial_happy_path(...)
+def test_batch_run_and_save_overwrite_false_skips_recompute(...)
+def test_batch_run_and_save_invalid_roi_reports_error(...)
```

## 5) Search confirmation
I searched for `HRBatchSaveResult`, `batch_run_and_save`, overwrite handling, backend handling, and save-worker entry points, and only changed the in-scope files.

## 6) Validation (commands actually run)
- `python3 -m py_compile heart_rate_batch.py tests/test_heart_rate_batch_save.py`
- `uv run pytest -q`
- `/Users/cudmore/Sites/kymflow_outer/kymflow/.venv/bin/python -c "from heart_rate_batch import batch_run_and_save, HRBatchSaveResult; print('ok')"`

## 7) Expected validation markers
- `uv run pytest -q` should pass all tests (current run: `26 passed, 1 warning`).
- Import check prints `ok`.
- Happy-path test creates one saved JSON (`*_heart_rate.json`) and loading it yields both ROI ids.

## 8) Summary of changes
- Added KISS save-oriented batch API `batch_run_and_save(...)`.
- Added new per-file status dataclass `HRBatchSaveResult`.
- Implemented serial/thread/process orchestration that preserves input order.
- Added overwrite skip behavior (`overwrite=False` returns success with existing output path).
- Added per-file error capture behavior (returns `ok=False`, fills `error`, continues).
- Added tests for required serial happy path, overwrite skip, and invalid-roi error reporting.

## 9) Risks / tradeoffs
- Process/thread backends are minimally covered in tests (ticket requested serial-focused tests only).
- Per-file errors are converted to result records, so callers must inspect `ok`/`error`.
- Logging is warning-level for per-file failures; repeated large failures could be noisy.

## 10) Self-critique
### Pros
- API matches ticket intent: one-call analyze+save across many CSVs.
- No algorithm or schema changes.
- Robust per-file fault isolation with ordered outputs.

### Cons
- No additional docs file was added (optional item).
- Backend-specific performance characteristics are not benchmarked here.

### Drift risk
- Low: orchestration layer only, reusing existing analysis/persistence APIs.

### Red flags / architectural violations (if any)
- None identified.
