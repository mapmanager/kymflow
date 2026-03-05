# Ticket 038 — Negative tests for tolerant extras + strict diameter schema (CSV/JSON load)

## Goal
Harden the load path so we **fail fast** when required analysis fields are missing/invalid, while still allowing “extra/unrelated” columns to exist without breaking loads.

This ticket adds **tests only + minimal helper changes** (if needed) to make the tests pass. No algorithm changes.

## Policy
- **Fail fast** for missing/invalid *required* diameter fields (no defaults, no coercion).
- **Tolerate unrelated extra columns** in CSV/JSON.
- **Strict** only for columns that look like our diameter schema (i.e. match the `*_roi{roi}_ch{ch}` pattern or are otherwise known registry columns).

## Scope
- Focus on the current diameter analysis persistence in `diameter_analysis.py` and its tests.
- Use the registry (or central column spec) as the single source of truth.

## Acceptance criteria
### A. Unknown columns behavior (tolerant extras, strict schema)
1. Loading a CSV that includes unrelated extra columns (e.g. `notes`, `foo`, `bar`) **succeeds**.
2. Loading a CSV that includes columns that **match the diameter pattern** `*_roi{roi}_ch{ch}` but the base field name is not in the registry/spec **fails** with a clear error.

### B. Missing required columns must fail
3. Remove one required column (e.g. `diameter_px_roi1_ch1`) from a fixture CSV → load **raises** immediately.
4. Remove `time_s` (or whatever is required as time index) → load **raises** immediately.

### C. Missing required IDs must fail
5. JSON load: remove `roi_id` or `channel_id` for a run → load **raises** (no defaults).
6. CSV load: if run reconstruction requires roi/channel identity, ensure missing/invalid roi/channel in column names causes a **hard failure**.

### D. No implicit defaults / coercions
7. Add a negative test proving `from_row` (or equivalent) does **not** default `channel_id` (or roi_id) when missing.

## Implementation notes
- Prefer parametrized pytest tests with small fixture generators.
- Use `pytest.raises(ValueError, match=...)` (or the project’s chosen exception type) with a **specific message** so failures are actionable.
- If any loader still defaults values, remove the default behavior and update tests accordingly.

## Files likely involved
- `sandbox/diameter-analysis/diameter_analysis.py`
- `sandbox/diameter-analysis/tests/test_multi_run_serialization.py` (or new dedicated tests)
- Possibly add `tests/test_negative_load_cases.py` if cleaner.

## Out of scope
- Any GUI changes
- Any detection algorithm changes
