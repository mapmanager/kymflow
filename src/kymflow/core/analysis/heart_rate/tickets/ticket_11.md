# Ticket 11 — Parallel Batch HR + Persistence + DF Init (Scoped, No Runner Changes)

**Ticket ID:** ticket_11  
**Scope folder (STRICT):** `kymflow/sandbox/heart_rate_analysis/heart_rate/`  
**Allowed edits (only these files, unless explicitly created below):**
- ✅ Modify: `heart_rate_analysis.py`
- ✅ Create: `heart_rate_batch.py`
- ✅ Modify/Create tests under: `tests/` (create if missing), e.g. `tests/test_heart_rate_batch.py`

**Out of scope (DO NOT TOUCH):**
- ❌ `run_heart_rate_examples_fixed2.py` (no edits)
- ❌ Any files outside the scope folder above
- ❌ Any CLI parsing / UI code

---

## Goal

1) Add a **DataFrame-first** initialization pathway for `HeartRateAnalysis` (for GUI/runtime where CSV already loaded).  
2) Add **save/load of computed HR results + per-ROI config** to JSON (`*_heart_rate.json`) next to the CSV.  
3) Add **batch parallel execution** API with **two backends**:
   - `backend="process"`: CSV-path tasks only (STRICT — raise `ValueError` if any df-based task is passed).
   - `backend="thread"`: can accept df-based tasks or csv-path tasks.
4) Provide a helper to convert batch results → a DataFrame of summaries (`minimal="mini"` supported).

**Important:** No duplicate algorithm code. The batch runner must reuse a single compute core.

---

## Definitions / Invariants

### Persistence filename convention (locked)
- For `somefile.csv` → default JSON path is `somefile_heart_rate.json` in the same folder.

### ROI rules (locked)
- `roi_id` column **must exist** in the input table. If not, raise `ValueError` with a clear message.
- JSON artifact contains **all analyzed ROIs** for that CSV in one file.

### Compute-only (locked)
- Batch runner does **not** auto-save JSON. Saving remains explicit via `save_results_json(...)`.

---

## Part A — HeartRateAnalysis: init-from-df + persistence

### A1) DF initializer
Update `HeartRateAnalysis` to support:
- `__init__(self, df: pandas.DataFrame, *, source_path: Optional[pathlib.Path] = None)`
- Keep `@classmethod from_csv(cls, path: Path) -> HeartRateAnalysis` as convenience.

Requirements:
- Enforce presence of ROI column on init:
  - If `roi_id` column missing: raise `ValueError("... roi_id ...")`
- Treat `df` as **read-only** (no in-place mutation of caller df). If internal cleaning is required, copy explicitly.

### A2) Persistence API
Add methods to `HeartRateAnalysis`:

- `def default_results_json_path(self) -> Path:`
  - Requires `self.source_path` be set; else raise `ValueError`.
  - Implement naming: `<csv_stem>_heart_rate.json`

- `def save_results_json(self, path: Optional[Path] = None) -> Path:`
  - Saves a JSON containing:
    - schema_version (int)
    - source_csv (string path if available)
    - saved_at_iso (string)
    - per_roi: mapping from roi_id (string or int) → object containing:
      - cfg: HRAnalysisConfig serialized (explicit to_dict; NOT free-form dict)
      - results: HeartRatePerRoiResults serialized (explicit to_dict)
  - Returns the actual path written.

- `def load_results_json(self, path: Optional[Path] = None) -> None:`
  - Loads JSON and populates:
    - `self.results_by_roi[roi_id]`
    - `self.cfg_by_roi[roi_id]` (or, if cfg now lives inside results, populate `results.cfg` and keep cfg_by_roi consistent with current architecture)
  - Validate schema_version and required keys.
  - Should not require recomputation.

Serialization requirements:
- If `to_dict()/from_dict()` patterns already exist for:
  - `HRAnalysisConfig`
  - `HeartRateEstimate`
  - `HeartRatePerRoiResults`
  use them; if missing, add them in `heart_rate_analysis.py` with typed signatures and Google docstrings.

---

## Part B — Batch runner (NEW FILE): heart_rate_batch.py

### B1) Task model
Add a dataclass:

```python
@dataclass(frozen=True)
class HRBatchTask:
    csv_path: Optional[Path] = None
    df: Optional[pd.DataFrame] = None
    source_id: Optional[str] = None
    roi_ids: Optional[Sequence[int]] = None
    cfg: Optional[HRAnalysisConfig] = None
```

Rules:
- Exactly one of `csv_path` or `df` must be provided.
- If `df` is provided and `source_id` is None, set a default like `"<df>"` (but encourage callers to set it).

### B2) Result model
Define:

```python
@dataclass(frozen=True)
class HeartRateFileResult:
    source_id: str
    per_roi: dict[int, HeartRatePerRoiResults]
```

### B3) Core compute functions
Implement as pure functions:

- `compute_hr_for_df(df: pd.DataFrame, *, roi_ids: Optional[Sequence[int]], cfg: HRAnalysisConfig) -> HeartRateFileResult`
  - If roi_ids is None: sorted unique from df["roi_id"].
  - Creates HeartRateAnalysis(df, source_path=None) and runs requested ROIs.
  - Returns structured result.

- `compute_hr_for_csv(csv_path: Path, *, roi_ids: Optional[Sequence[int]], cfg: HRAnalysisConfig) -> HeartRateFileResult`
  - Loads CSV to df, then calls `compute_hr_for_df(...)`.
  - Sets `source_id` to `str(csv_path)`.

### B4) Batch runner API
Implement:

```python
def run_hr_batch(
    tasks: Sequence[HRBatchTask],
    *,
    default_cfg: Optional[HRAnalysisConfig] = None,
    n_workers: int = 0,
    backend: Literal["process", "thread"] = "process",
) -> list[HeartRateFileResult]:
```

Rules:
- If default_cfg is None: use `HRAnalysisConfig()`.
- For each task: cfg = task.cfg or default_cfg.
- `backend="process"`:
  - STRICTLY require every task has `csv_path` and `df is None`.
  - If any df-task found → raise `ValueError` with a clear message.
  - Use `concurrent.futures.ProcessPoolExecutor`.
- `backend="thread"`:
  - Use `ThreadPoolExecutor`.
  - Allow df tasks and csv tasks.

Implementation notes:
- Keep process worker function at module top-level (pickleable).
- Do not capture non-pickleable state.

### B5) DataFrame helper
Add:

```python
def batch_results_to_dataframe(
    results: Sequence[HeartRateFileResult],
    *,
    roi_id: Optional[int] = None,
    minimal: Literal["mini", "full"] = "mini",
) -> pd.DataFrame:
```

- If roi_id is None: one row per (source_id, roi_id) for all rois.
- If roi_id set: include only that ROI when present.
- For minimal="mini": use existing per-ROI “mini summary” schema:
  - file/source_id, roi_id, valid_frac,
  - lomb/welch bpm/hz/snr,
  - agree_delta_bpm, agree_ok,
  - status, status_note
- Ensure consistent columns across rows.

---

## Part C — Tests

Create tests under `tests/` that verify:

1) DF init + ROI enforcement (missing roi_id → ValueError).
2) JSON persistence round-trip for one roi.
3) Batch runner thread backend supports df tasks.
4) Batch runner process backend rejects df tasks (ValueError).

Use small synthetic dataframes; tests must be deterministic and fast.

---

## Documentation requirements

All new/modified public functions/classes must have:
- fully typed signatures
- Google-style docstrings (Args/Returns/Raises)

---

## Acceptance criteria

- `uv run pytest` passes for tests under scope.
- Import works: `from heart_rate_batch import run_hr_batch, HRBatchTask`
- No changes to runner script.
- No edits outside allowed files.
