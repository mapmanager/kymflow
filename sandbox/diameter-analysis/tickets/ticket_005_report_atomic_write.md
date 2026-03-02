# ticket_005.md — Make Codex reports atomic and avoid 0-byte placeholders

## Mode
Strict

## Context
We have repeatedly observed this failure mode:
- Codex attempts to write `tickets/<ticket>_codex_report.md` but leaves it as **0 bytes** (partial write).
- Then, due to no-overwrite rules, Codex writes the real report as `_v2.md`.

We want to prevent this by requiring **atomic report writes** (write to tmp → rename) and clarifying how to treat 0-byte reports.

## Scope (STRICT)

### Allowed edits
- `kymflow/sandbox/diameter-analysis/tickets/**`

### Forbidden edits
- Anything outside `kymflow/sandbox/diameter-analysis/tickets/`

## Requirements

### R1) Update CODEX_RULES.md (HARD)
Edit `tickets/CODEX_RULES.md` to add:

1) **Atomic write rule (HARD)** for reports:
   - Determine final report path (base or `_vN`).
   - Write report content to `<final_path>.tmp` first.
   - Verify tmp is non-empty.
   - Rename/move tmp → final path (atomic within same folder).

2) **0-byte report handling**:
   - If the target report file exists but is 0 bytes, it is considered a partial/failed write.
   - Codex MAY reuse/overwrite that 0-byte file (preferred), OR delete it and write the base path.
   - Never overwrite a non-empty report.

3) **Operator note**:
   - “If a 0-byte base report exists, it may be safely deleted; `_v2` (or higher) is authoritative.”

### R2) Update TICKET_TEMPLATE.md
Edit `tickets/TICKET_TEMPLATE.md` report section so it mirrors the updated CODEX_RULES.md guidance:
- Ticket-filename-derived report naming
- No-overwrite `_v2+`
- Atomic write rule (tmp → rename)
- 0-byte report handling

### R3) Validation
In the report, include:
- A short “before/after” snippet showing the new atomic write + 0-byte policy wording exists in both files.
- A search confirmation that there are no remaining mentions of the older ambiguous `tickets/<ticket_name>_codex_report.md` pattern.

## Acceptance criteria
- CODEX_RULES.md includes atomic write rule + 0-byte handling + operator note.
- TICKET_TEMPLATE.md includes the same guidance.
- No edits outside `tickets/**`.

## Validation commands
- `uv run python -c "from pathlib import Path; import re; p=Path('kymflow/sandbox/diameter-analysis/tickets'); txt='\n'.join(x.read_text(encoding='utf-8') for x in p.glob('*.md')); assert 'atomic' in txt.lower(); assert ('0 bytes' in txt.lower()) or ('0-byte' in txt.lower()); assert 'tmp' in txt.lower();"` 

## Codex implementation report
Save:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_005_report_atomic_write_codex_report.md`
