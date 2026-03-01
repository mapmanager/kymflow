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
Never overwrite an existing report.
