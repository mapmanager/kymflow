# ticket_X.md — <Short Title>

## Mode
Strict | Refactor | Exploration

## Context
- What prompted this ticket?
- What user-visible behavior is desired?

## Scope (STRICT)
### Allowed edits
- <list files/folders>

### Forbidden edits
- <list files/folders>

## Requirements
R1: ...
R2: ...
R3: ...

## Acceptance criteria
- What must be true after completion?
- Commands that must pass

## Validation commands
- `uv run pytest -q`
- `uv run python ...`

## Notes / constraints
- Any invariants (keys, schema) that must remain stable
- Any “do not change” constraints

## Codex implementation report
Save report as:
- `tickets/<this_ticket_filename_without_.md>_codex_report.md`
If that file exists, save as:
- `tickets/<this_ticket_filename_without_.md>_codex_report_v2.md` (or higher)
Never overwrite an existing non-empty report.
If the base report file exists but is 0 bytes (partial write), you may reuse/overwrite that 0-byte path (or delete it and reuse base).
Always write atomically:
- write to `tickets/<derived_report_name>.tmp` first,
- verify tmp file is non-empty,
- then rename tmp to final report path in the same folder.
