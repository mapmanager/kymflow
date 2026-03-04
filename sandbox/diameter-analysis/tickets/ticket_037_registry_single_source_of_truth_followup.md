# Ticket 037 — Wide CSV registry is single source of truth (follow-up to Ticket 032)

## Goal
Make the **registry** the single source of truth for wide CSV columns and parsing, and enforce drift-safety with tests.

## Scope
- Focus strictly on “registry-driven wide CSV” invariants.
- Do **not** change analysis outputs or numeric behavior.
- No backward-compat defaults unless explicitly specified in this ticket (none are).

## Requirements
1. **Single pathway for column generation**
   - All code that emits wide CSV columns must call:
     - `registry.columns()` (or equivalent canonical function)
   - No ad-hoc `f"{field}_roi{...}_ch{...}"` string building outside the registry.

2. **Single pathway for parsing columns**
   - All code that reads wide CSV must call:
     - `registry.parse_columns(...)` (or equivalent canonical function)
   - No duplicated regex parsing logic outside the registry.

3. **Unknown-field rejection**
   - If a wide CSV contains any columns matching the wide pattern that are not in the registry:
     - Fail fast with a clear error listing unknown columns.
   - If the CSV has extra unrelated columns that do not match the wide pattern:
     - Either ignore, or explicitly list what is allowed (choose one; default to ignore unrelated).

4. **Tests**
   - Add a test that fails if an unknown wide-field appears:
     - Construct a fake header with one invalid field like `bogus_field_roi1_ch1` and ensure parsing raises.
   - Add a snapshot-ish test for `registry.columns()`:
     - Either explicitly list expected columns for a small fixture set (roi=1, ch=1),
       or assert the set is stable and contains required core columns.
   - Keep tests deterministic.

## Files to touch (exact paths may differ; update to match repo)
- `diameter_analysis.py` (registry + csv emit/parse call sites)
- `tests/test_multi_run_serialization.py` (or dedicated new test file)
- `docs/multi_run_serialization.md` if it currently documents behavior inconsistent with the implementation.

## Acceptance criteria
- `uv run pytest` passes
- Wide CSV writing uses registry only (no ad-hoc string building outside registry)
- Wide CSV reading uses registry only (no ad-hoc parsing outside registry)
- Unknown wide fields trigger a fail-fast error in tests.
