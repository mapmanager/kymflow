# Prompts Folder Guide

`prompts/` stores operational prompt assets used to plan, execute, and review zarr-core ticket work.

## Subfolders
1. `prompts/runners/`
   - Execution templates and shared report specs.
   - Examples: `codex_run_ticket.md`, `codex_implement_ticket_and_gen_report_prompt.md`, `codex_change_report_prompt.md`.

2. `prompts/tickets/`
   - Ticket specs (`codex_ticket_*.md`, `codex_tickets_1_2.md`) and their generated change reports (`*_change_report.md`).

3. `prompts/handoffs/`
   - Larger architecture/design handoff packets and their change reports.

4. `prompts/archive/`
   - Optional long-term storage for retired or superseded prompt assets.

## Standard Workflow
1. A ticket is authored and saved under `prompts/tickets/`.
2. Run it through Codex using `prompts/runners/codex_run_ticket.md`.
3. Codex writes the change report next to the ticket file in `prompts/tickets/`.
4. Review the change report in ChatGPT, then iterate with follow-up tickets if needed.

## Codex Invocation Pattern
Use `prompts/runners/codex_run_ticket.md`

Set:
    `<TICKET_MD_PATH> = prompts/tickets/<ticket-file>.md`

Proceed.
