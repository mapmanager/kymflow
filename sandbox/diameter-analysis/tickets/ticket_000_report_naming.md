# ticket_000.md — Enforce report naming + no-overwrite rule in governance templates

## Mode
Strict

## Context
Codex reports must never overwrite previously saved `*_codex_report.md` files, and the report filename must be derived from the exact ticket filename (including suffixes like `_hardened`). We will enforce this by updating governance templates in:
- `kymflow/sandbox/diameter-analysis/tickets/CODEX_RULES.md`
- `kymflow/sandbox/diameter-analysis/tickets/TICKET_TEMPLATE.md`

This ticket introduces:
1) A deterministic report naming rule based on the ticket filename.
2) A mandatory “no overwrite” rule with `_v2`, `_v3`, ... suffixing when a report already exists.

## Scope (STRICT)

### Allowed edits
- `kymflow/sandbox/diameter-analysis/tickets/**`

### Forbidden edits
- Anything outside `kymflow/sandbox/diameter-analysis/tickets/`

## Requirements
R1: Update `kymflow/sandbox/diameter-analysis/tickets/CODEX_RULES.md` to include **HARD** rules:

### Report filename rule (HARD)
- Let the ticket file path be `kymflow/sandbox/diameter-analysis/tickets/<ticket_file>.md`
- The report filename MUST be:
  - `kymflow/sandbox/diameter-analysis/tickets/<ticket_file>_codex_report.md`
  - where `<ticket_file>` is the ticket basename **without** the `.md` extension.
  - Example:
    - Ticket: `ticket_002_hardened.md`
    - Report: `ticket_002_hardened_codex_report.md`

### No-overwrite rule (HARD)
- If the target report file already exists, Codex MUST NOT overwrite it.
- Instead, Codex MUST write:
  - `<ticket_file>_codex_report_v2.md`
  - or v3, v4, ... incrementing until an unused filename is found.
- The report content MUST include the final report path that was written.

R2: Update `kymflow/sandbox/diameter-analysis/tickets/TICKET_TEMPLATE.md` so the “Codex implementation report” section reads unambiguously:

- Save report as:
  - `tickets/<this_ticket_filename_without_.md>_codex_report.md`
- If that file exists, save as:
  - `tickets/<this_ticket_filename_without_.md>_codex_report_v2.md` (or higher)
- Never overwrite an existing report.

R3: Add a short note (1–3 bullets) to CODEX_RULES.md reminding the operator:
- “If you rename a ticket file, the report name changes accordingly.”
- “Do not copy/paste report paths into tickets; rely on the rule.”

R4: Ensure no other parts of these documents conflict with the new rules (search for `codex_report` and update references consistently).

## Acceptance criteria
- Both files are updated with the new rules.
- Search within `kymflow/sandbox/diameter-analysis/tickets/` confirms:
  - no remaining instruction that suggests `tickets/<ticket_name>_codex_report.md` (ambiguous)
  - all guidance matches the new ticket-filename-derived rule.
- No edits outside scope.

## Validation commands
- `uv run python -c "from pathlib import Path; import re; p=Path('kymflow/sandbox/diameter-analysis/tickets'); txt='\n'.join(x.read_text(encoding='utf-8') for x in p.glob('*.md')); assert 'codex_report_v2' in txt; assert re.search(r'ticket_002_hardened.*codex_report', txt, flags=re.I)"`

## Codex implementation report
Save:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_000_report_naming_codex_report.md`
