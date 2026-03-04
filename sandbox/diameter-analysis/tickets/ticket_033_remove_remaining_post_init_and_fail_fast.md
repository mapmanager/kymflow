# Ticket 033 — Remove remaining __post_init__ coercions; keep explicit validation only (fail fast)

**Goal:** Eliminate *silent coercion* in dataclasses inside `sandbox/diameter-analysis/` (especially `diameter_analysis.py`). Keep validation, but make it **fail fast** when required fields are missing/invalid. No backward-compat defaults.

## Scope
- **Only** touch code under `sandbox/diameter-analysis/` (not `kymflow/`).
- Focus file: `diameter_analysis.py`
- Update/extend tests as needed (preferably in `tests/`).

## Why
We now treat ROI/channel context and serialization fields as **required**. Silent coercion inside `__post_init__` can hide pipeline bugs and produce ambiguous/incorrect saved artifacts.

## Tasks

### 1) Inventory remaining __post_init__ methods
In `diameter_analysis.py`, locate all dataclasses with `__post_init__`.

For each, classify behavior as:
- **Validation-only** (acceptable): asserts type/range and raises on invalid.
- **Coercion** (remove): converting strings to ints, defaulting missing IDs, silently fixing shapes, etc.

### 2) Remove coercion from __post_init__
For any `__post_init__` that performs coercion:
- Remove the coercion.
- Replace with explicit checks that raise `TypeError` / `ValueError` with clear messages.
- If coercion was only there to support “old CSVs/JSON”, **delete that compatibility**.

### 3) Move validation to construction boundaries (where appropriate)
If a dataclass is created from untyped sources (dict/row):
- Keep the dataclass strict.
- Put any parsing/validation in the explicit constructor helpers (e.g., `from_row`, `from_dict`) and **fail fast** on missing required keys.

### 4) Tighten typing for required fields
Any field that is now required in the pipeline should:
- Not be `Optional[...]` unless there is a concrete, current use-case for `None`.
- Not be defaulted in serializers/deserializers.

### 5) Update tests to enforce “no silent coercion”
Add/extend tests to verify:
- Passing bad types raises (e.g., roi_id as "1" should raise, not coerce).
- Missing required keys in `from_row` / `from_dict` raises KeyError/ValueError.
- Serialization roundtrip does not introduce None/defaults for required fields.

## Acceptance criteria
- No dataclass silently coerces required fields at runtime.
- All tests pass: `uv run pytest`.
- Clear error messages when required fields are missing/invalid.
