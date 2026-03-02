# ticket_008.md — DRY dataclass serialization helpers (avoid brittle manual to_dict/from_dict)

## Mode
Strict

## Context
We have multiple dataclasses with manual `to_dict()` / `from_dict()` implementations that repeat field lists and casting. Example:

- `PostFilterParams.to_dict()` manually enumerates keys and casts
- `PostFilterParams.from_dict()` repeats defaults and type conversions

This is brittle: adding/removing/renaming a dataclass attribute requires remembering to update multiple places, violating DRY/KISS.

We want a small, explicit serialization helper that:
- serializes dataclasses by iterating `dataclasses.fields()`
- handles Enums (serialize as `.value`, parse from value)
- supports nested dataclasses (recursively) where present
- supports forward-compatible loading: ignore unknown keys
- supports stable defaults: missing keys use dataclass defaults
- avoids over-engineering (no pydantic)

Then refactor `PostFilterParams` (and any other params dataclasses in this sandbox that currently have brittle manual mapping) to use the helper.

## Scope (STRICT)

### Allowed edits
- `kymflow/sandbox/diameter-analysis/**`

### Forbidden edits
- Anything outside `kymflow/sandbox/diameter-analysis/`

## Requirements

### R1) Add a small serialization module
Create a new module, e.g.:
- `kymflow/sandbox/diameter-analysis/serialization.py`

Implement:

#### `dataclass_to_dict(obj) -> dict[str, Any]`
- Requires `dataclasses.is_dataclass(obj)`.
- Iterate `dataclasses.fields(obj)` and serialize each value:
  - Enum -> `value`
  - dataclass -> recurse
  - numpy scalar -> convert to python scalar (optional but helpful)
  - plain types -> pass through
- Return mapping of field_name -> serialized_value

#### `dataclass_from_dict(cls, payload: dict[str, Any]) -> cls`
- Requires `cls` is a dataclass type.
- Create kwargs by iterating dataclass fields:
  - if key missing: omit kwarg (so default applies)
  - if key present:
    - if field type is Enum subclass: parse via Enum(value)
    - if field type is dataclass: recurse
    - else: attempt simple cast for int/float/bool/str where safe; otherwise pass through
- Ignore unknown keys in payload.
- Raise a clear error for invalid Enum values.

Notes:
- Use `typing.get_origin/get_args` to handle `Optional[T]` for Enums (if needed).
- Keep it minimal; support what we use in this sandbox.

### R2) Refactor PostFilterParams
In `diameter_analysis.py`:
- Replace manual `to_dict()` with `return dataclass_to_dict(self)` (plus any small tweaks if needed).
- Replace manual `from_dict()` with `return dataclass_from_dict(cls, payload)` or an explicit wrapper that calls the helper.

Keep `__post_init__` validation (odd kernel size) intact.

### R3) Refactor other params dataclasses in this sandbox (best-effort)
Search within `kymflow/sandbox/diameter-analysis/` for other dataclasses with manual to_dict/from_dict of the same style (e.g., detection params, synthetic params).
- If low-risk, refactor them to use the helper too.
- If risky (special cases), leave them and document why in the report.

### R4) Tests
Add tests to ensure:
- Roundtrip: `obj -> to_dict -> from_dict` yields equal object for PostFilterParams
- Unknown keys in payload are ignored
- Invalid enum value raises a clear ValueError
- Defaults apply when keys missing

### R5) Documentation / Codex rule note
Add a short note to `docs/dev_notes.md` (or appropriate doc) stating:
- “Prefer serialization helper over hand-written to_dict/from_dict for params dataclasses.”

## Acceptance criteria
- `uv run pytest -q` passes.
- PostFilterParams no longer manually enumerates fields in to_dict/from_dict.
- Helper exists and is used at least for PostFilterParams (and optionally other params dataclasses).
- Tests cover roundtrip + unknown keys + invalid enum.

## Validation commands
- `uv run pytest -q`

## Codex implementation report
Save:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_008_dataclass_serialization_refactor_codex_report.md`
