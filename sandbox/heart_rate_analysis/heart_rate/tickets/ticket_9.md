# ticket_9.md — Structured status codes + “mini” summary schema for batch runs

## Context
Folder boundary (HARD):
kymflow/sandbox/heart_rate_analysis/heart_rate/

We currently produce a compact per-ROI summary dict, but:
- status logic still relies on **string reasons** in some places (fragile)
- the “compact” summary is still too wide for your 400-file batch table

This ticket:
1) introduces **structured status/failure codes** (Enum/Literal) end-to-end
2) adds a more minimal **“mini”** summary schema intended for batch reporting

## Scope (STRICT)

### Allowed edits
- heart_rate_analysis.py
- heart_rate_pipeline.py
- run_heart_rate_examples_fixed2.py
- tests/ (add/modify tests)
- docs/ (add/modify markdown docs)
- tickets/ (report file only)

### Forbidden edits
- heart_rate_plots.py (do not modify)
- Any file outside kymflow/sandbox/heart_rate_analysis/heart_rate/

## Requirements

### R1 — Add structured status/failure codes

Create a new enum in an appropriate module (prefer `heart_rate_pipeline.py`):

```python
class HRStatus(str, Enum):
    OK = "ok"
    INSUFFICIENT_VALID = "insufficient_valid"
    NO_PEAK_LOMB = "no_peak_lomb"
    NO_PEAK_WELCH = "no_peak_welch"
    METHOD_DISAGREE = "method_disagree"
    OTHER_ERROR = "other_error"
```

Rules:
- Use this enum wherever we currently store or infer `status`.
- `status_note` may remain as a *human-readable* string, but **status itself must never be inferred from strings**.

### R2 — Estimator returns structured outcome (no string parsing)

Update the relevant estimator(s) in `heart_rate_analysis.py` so callers can distinguish failure modes without parsing text.

Minimum acceptable implementation:
- Keep existing return shape, but include a **structured code** in debug dict:
  - `dbg["status"] = HRStatus.<...>.value` or `HRStatus.<...>`
- Preferably, return an explicit outcome object, e.g.:

```python
@dataclass(frozen=True)
class HREstimateOutcome:
    estimate: Optional[HeartRateEstimate]
    status: HRStatus
    note: str = ""
```

If you introduce an outcome object:
- update pipeline code accordingly
- keep backward compatibility inside the sandbox by updating all callers in-scope

No string-based branching allowed for status.

### R3 — Agreement logic uses structured status
In pipeline summary generation:
- `METHOD_DISAGREE` is set only when:
  - both methods produced an estimate, and
  - `agree_delta_bpm > agree_tol_bpm`
- If only one method produced an estimate:
  - overall status should be `OK` (default policy for Milestone 1)
  - but the missing method should be reflected in method-specific status in the richer internal results (not necessarily in the mini summary)

### R4 — Add “mini” summary schema (batch table friendly)

Add a new API method (or extend `get_roi_summary`) to support:

- `get_roi_summary(..., minimal=True)` (existing) and
- `get_roi_summary(..., minimal="mini")` (new), OR
- `get_roi_summary_mini(roi_id: int) -> dict`

**Mini schema keys (target)**
(keep this stable; do not include extra keys):

Required keys:
- `file` (basename only, not full path)
- `roi_id`
- `valid_frac`
- `lomb_bpm` (or None)
- `lomb_snr` (or None)
- `welch_bpm` (or None)
- `welch_snr` (or None)
- `agree_delta_bpm` (or None)
- `agree_ok` (or None)
- `status` (HRStatus value string)

Optional key (only include when status != OK):
- `status_note` (short)

Do NOT include:
- hz, edge flags, band concentration, n_total/n_valid, t_min/t_max in mini summary

Notes:
- `file` should be `Path(path).name` so batch tables stay readable.
- JSON-serializable (enums should be `.value` strings).

### R5 — Runner prints mini summary
In `run_heart_rate_examples_fixed2.py`:
- print the **mini** summary dict by default
- keep the plots behavior unchanged

### R6 — Docs
Update/add docs:
- `docs/status_codes.md` — list HRStatus values and what they mean
- Update `docs/batch_summary_schema.md` to include the mini schema

### R7 — Tests
Add/extend tests to cover:
- HRStatus enum exists and is used in summaries
- mini summary has exactly the expected key set (plus optional status_note only when needed)
- agreement status becomes METHOD_DISAGREE when delta exceeds tolerance
- no code path infers status by parsing strings (best-effort: test should not depend on substrings of notes)

Run:
- `uv run pytest -q`

## Acceptance criteria
- Mini summary for the example file looks roughly like:

```python
{
  "file": "20251014_A98_0002_kymanalysis.csv",
  "roi_id": 1,
  "valid_frac": 0.4666,
  "lomb_bpm": 437.3,
  "lomb_snr": 19.78,
  "welch_bpm": 449.9,
  "welch_snr": 2.11,
  "agree_delta_bpm": 12.67,
  "agree_ok": True,
  "status": "ok",
}
```

- `uv run python run_heart_rate_examples_fixed2.py` runs
- `uv run pytest -q` passes

## Codex implementation report
Save:
- tickets/ticket_9_codex_report.md
