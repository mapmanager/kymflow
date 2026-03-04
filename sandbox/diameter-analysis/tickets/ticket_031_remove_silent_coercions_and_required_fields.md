# ticket_031_remove_silent_coercions_and_make_required_fields_nonoptional.md

## Goal
Remove defensive “silent coercion / back-compat defaults” in the diameter pipeline for required fields:
- `roi_id`
- `channel_id`
- `roi_bounds`

These are required at analysis entry; therefore they must remain required in:
- result objects
- CSV/JSON serialization
- loaders/reconstructors

## Scope
- Work only inside `sandbox/diameter-analysis/`.
- No backward compatibility: do not use `row.get(..., default)` for required fields.
- Prefer fail-fast: missing required fields should raise immediately.

## Tasks

### 1) Make required fields non-optional in result types
- Change `DiameterResult.roi_id` and `DiameterResult.channel_id` to plain `int` (non-Optional).
- Remove any `__post_init__` logic that silently coerces/patches IDs.
  - If validation is needed, validate and raise (do not coerce).
- Ensure any construction site passes the required IDs explicitly.

### 2) Remove loader defaults
- In any `from_row(...)` / `from_wide_row(...)` paths:
  - Replace `row.get("channel_id", ...)` patterns with `row["channel_id"]`.
  - Raise on missing keys / invalid values.

### 3) Wide CSV generation contract cleanup
If wide CSV reconstruction requires `center_row`, then:
- Remove/disable any option (e.g. `include_time=False`) that generates a wide CSV that **cannot** be loaded later.
- Ensure wide CSV always includes a time column (e.g. `time_s`) and any other required index columns.

### 4) Add schema-tightening tests
Add tests that verify:
- Missing `roi_id` or `channel_id` in CSV rows raises immediately.
- Any attempt to build a wide CSV without required fields fails fast.

## Acceptance criteria
- No Optional typing for required IDs.
- No silent defaults/coercions for required IDs in serialization/deserialization.
- Tests cover “missing required fields” failure modes.
