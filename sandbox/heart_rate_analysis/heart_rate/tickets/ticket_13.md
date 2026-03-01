# Ticket 13 — Add KISS batch_run_and_save() API (analyze + save per CSV)

**Ticket ID:** ticket_13  
**Scope folder (STRICT):** `kymflow/sandbox/heart_rate_analysis/heart_rate/`

## Allowed edits (ONLY these files, unless explicitly created below)
- ✅ Modify: `heart_rate_batch.py`
- ✅ Modify/Create tests under: `tests/` (e.g. `tests/test_heart_rate_batch_save.py`)
- ✅ (Optional) Add doc: `docs/heart_rate_batch.md`

## Out of scope (DO NOT TOUCH)
- ❌ `run_heart_rate_examples_fixed2.py`
- ❌ Any files outside the scope folder above
- ❌ No changes to HR numerical algorithms (only orchestration)
- ❌ No changes to JSON schema of saved results (must remain compatible)

---

## Intent

Provide a **dead-simple public API** for batch processing:

> Given a list of CSV paths, run HR analysis for each CSV (all ROI ids or a provided subset) and **save** results JSON next to each CSV.

Caller should not manage pools/executors, flattening, joins, or per-file loops.

---

## New public API (required)

In `heart_rate_batch.py`, add:

### A) Result record
```python
@dataclass(frozen=True)
class HRBatchSaveResult:
    csv_path: Path
    ok: bool
    saved_json_path: Optional[Path]
    error: str = ""
```

### B) Batch runner
```python
def batch_run_and_save(
    csv_paths: Sequence[Path],
    *,
    roi_ids: Optional[Sequence[int]] = None,
    cfg: Optional[HRAnalysisConfig] = None,
    overwrite: bool = True,
    backend: Literal["process", "thread", "serial"] = "process",
    n_workers: int = 0,
) -> list[HRBatchSaveResult]:
    """Run HR analysis for each CSV and save results JSON next to the CSV.

    Behavior:
      - If roi_ids is None: analyze ALL roi_id values present in each CSV.
      - If cfg is None: use HRAnalysisConfig() dataclass defaults.
      - If cfg is provided: reuse the same cfg for every ROI in every CSV.

    Saving:
      - Saved artifact path: analysis.default_results_json_path() (i.e., ``<csv_stem>_heart_rate.json``).
      - If overwrite is False and artifact exists: do NOT recompute; return ok=True with saved_json_path pointing to existing file.

    Parallelism:
      - backend="serial": run in-process, deterministic (tests should use this).
      - backend="thread": thread pool for GUI-friendly use.
      - backend="process": process pool for batch speedups across files.

    Caller experience:
      - One function call; no pool management by caller.
      - Returns one HRBatchSaveResult per input CSV (preserve input order).

    Raises:
      - Should NOT raise for per-file failures; should record failures in HRBatchSaveResult.error and continue.
      - May raise ValueError for invalid inputs (empty csv_paths, invalid backend string, etc.).
    """
```

---

## Implementation details (constraints)

### 1) Worker function
Implement an internal worker that takes **one CSV path** and returns `HRBatchSaveResult`.
- It must:
  1) instantiate `HeartRateAnalysis.from_csv(csv_path)`
  2) choose ROI list:
     - `roi_ids` passed in → validate each exists in `analysis.roi_ids` (if not, error result)
     - `roi_ids is None` → `analysis.roi_ids`
  3) choose cfg:
     - `cfg is None` → `HRAnalysisConfig()`
     - else use provided cfg
  4) run analysis:
     - for each roi_id: `analysis.run_roi(roi_id, cfg=cfg_use)` (do not pass methods; class should default appropriately)
  5) save:
     - `out = analysis.default_results_json_path()`
     - `analysis.save_results_json(out)` (or save_results_json(path=out) depending on signature)
  6) return ok True with saved_json_path

### 2) Overwrite behavior
If overwrite=False and output json exists:
- skip recompute and return ok True.

### 3) Parallel backends
- Keep this minimal and robust.
- For thread/process pools:
  - dispatch one task per CSV (parallelize across files only)
  - preserve input order in returned list
- Tests will not cover thread/process, only serial.

### 4) Logging
- Use logging for per-file errors at warning level.
- Do not spam logs for every ROI by default.

---

## Tests (required)

Add `tests/test_heart_rate_batch_save.py` (or similar) covering:

### T1) Serial happy path (roi_ids=None, cfg=None)
- Create a temporary CSV with required columns including roi_id, time, velocity.
- Ensure it contains at least 2 distinct roi_id values.
- Call:
  - `batch_run_and_save([csv_path], roi_ids=None, cfg=None, backend="serial")`
- Assert:
  - result[0].ok is True
  - saved_json_path exists
  - Load JSON via `HeartRateAnalysis.from_csv(csv).load_results_json(saved_json_path)` and confirm:
    - `analysis.results_by_roi` has both roi ids.

### T2) overwrite=False skips recompute
- Run once to create JSON
- Run again with overwrite=False
- Assert ok True and saved_json_path same
- (No need to prove “no recompute” other than not raising; keep test simple)

### T3) invalid roi_ids reports error but does not raise
- Provide roi_ids containing a missing roi id
- Assert ok False and error contains useful message

Use small data (few dozen rows), deterministic.

---

## Optional documentation (nice-to-have)

`docs/heart_rate_batch.md`:
- Describe `batch_run_and_save` usage with 2–3 short examples.
- Mention backends and when to use (serial for tests; thread for GUI; process for batch).

---

## Acceptance criteria

- `uv run pytest` passes.
- New API exists and is importable.
- Serial backend works and saves one JSON per CSV with all ROI ids (when roi_ids=None).
- No changes to HR algorithm numerics or JSON schema.

---

## Codex report requirements (per CODEX_RULES)
- List modified code files (exclude report file), plus artifacts created
- Provide unified diffs for changed code files
- State what searches were performed to avoid unintended edits
- Provide commands run and observed outputs
- Include self-critique (pros/cons/drift risk)
