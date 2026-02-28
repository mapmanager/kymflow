# ticket_10.md — Mini summary: add per-method Hz + always include status_note key

## Context
Folder boundary (HARD):
kymflow/sandbox/heart_rate_analysis/heart_rate/

Ticket 9 introduced:
- `HRStatus` enum for structured status
- a minimal `"mini"` summary schema via `get_roi_summary(..., minimal="mini")`

Two refinements requested:
1) Include `*_hz` in the mini summary (users want peak frequency in Hz directly).
2) Always include `status_note` key (even when status == OK) so mini summaries have a stable set of columns
   for easy conversion to DataFrame/CSV.

## Scope (STRICT)

### Allowed edits
- heart_rate_pipeline.py
- run_heart_rate_examples_fixed2.py
- tests/ (add/modify tests)
- docs/ (add/modify markdown docs)

### Forbidden edits
- heart_rate_analysis.py (do not modify)
- heart_rate_plots.py (do not modify)
- Any file outside kymflow/sandbox/heart_rate_analysis/heart_rate/

## Requirements

### R1 — Mini summary adds `lomb_hz` and `welch_hz`
In the `"mini"` summary output, include:
- `lomb_hz` (float or None)
- `welch_hz` (float or None)

These should be the peak frequency in Hz corresponding to the detected HR peak for each method.

### R2 — Mini summary always includes `status_note`
In the `"mini"` summary output:
- Always include the key `status_note`
- Use `""` (empty string) when there is no note / status == OK

Rationale:
- Stable keys simplify batch table creation (list[dict] -> pandas DataFrame).

### R3 — Update docs
Update `docs/batch_summary_schema.md` to reflect the mini schema now includes:
- `lomb_hz`, `welch_hz`
- `status_note` always present (may be empty)

### R4 — Update tests
Update tests that assert mini schema keys:
- Ensure `lomb_hz` and `welch_hz` exist
- Ensure `status_note` always exists (empty string allowed)

Run:
- `uv run pytest -q`

### R5 — Runner prints updated mini summary
`run_heart_rate_examples_fixed2.py` should print the updated mini summary dict as it does now,
with the additional hz fields and always-present status_note.

## Acceptance criteria
Mini summary dict resembles:

```python
{
  "file": "20251014_A98_0002_kymanalysis.csv",
  "roi_id": 1,
  "valid_frac": 0.4666,
  "lomb_bpm": 437.3,
  "lomb_hz": 7.288,
  "lomb_snr": 19.78,
  "welch_bpm": 449.9,
  "welch_hz": 7.499,
  "welch_snr": 2.11,
  "agree_delta_bpm": 12.67,
  "agree_ok": True,
  "status": "ok",
  "status_note": "",
}
```

- `uv run pytest -q` passes
- `uv run python run_heart_rate_examples_fixed2.py` runs without error

## Codex implementation report
Save:
- tickets/ticket_10_codex_report.md
