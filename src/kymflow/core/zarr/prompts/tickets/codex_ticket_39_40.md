# codex_ticket_39_40.md

## Title
Reorganize `prompts/` into runners/tickets/handoffs + add `prompts/README.md`

Repo: `kymflow`
Branch: `kymflow-zarr`
Scope: `src/kymflow/core/zarr/prompts/**` only

---

## Why
The `prompts/` directory is mixing:
- execution runners (how to run tickets),
- tickets (work specs),
- change reports (outputs),
- handoffs (larger design packets).

We want a clean layout so future you (and other devs) can:
- find the right runner quickly,
- run any ticket consistently,
- locate historical tickets/reports easily.

---

## Ticket 39 — Create `prompts/README.md`

Add:

- `src/kymflow/core/zarr/prompts/README.md`

Must include:
- What `prompts/` is for
- The 4 subfolders and what belongs in each
- The standard workflow (brief):
  1) ticket is created (usually by ChatGPT + saved as `prompts/tickets/...`)
  2) run via Codex using `prompts/runners/codex_run_ticket.md`
  3) Codex writes a change report next to the ticket
  4) review change report in ChatGPT + iterate

- The exact Codex invocation pattern to run a ticket, e.g.:

  Use prompts/runners/codex_run_ticket.md

  Set:
      <TICKET_MD_PATH> = prompts/tickets/<ticket-file>.md

  Proceed.

(Use the actual placeholder names from the runner file after you update it in Ticket 40.)

---

## Ticket 40 — Reorganize prompt files into subfolders and update runner paths

### Create folders
- `src/kymflow/core/zarr/prompts/runners/`
- `src/kymflow/core/zarr/prompts/tickets/`
- `src/kymflow/core/zarr/prompts/handoffs/`

### Move files (git mv)
Move these runner templates:

- `prompts/codex_run_ticket.md` -> `prompts/runners/codex_run_ticket.md`
- `prompts/codex_change_report_prompt.md` -> `prompts/runners/codex_change_report_prompt.md`

Optional / recommended to reduce confusion:
- `prompts/codex_implement_ticket_and_gen_report_prompt.md` -> `prompts/runners/codex_implement_ticket_and_gen_report_prompt.md`

### Move ticket specs + change reports
Move all files matching:
- `prompts/codex_ticket_*.md` -> `prompts/tickets/`
- `prompts/codex_ticket_*_change_report.md` -> `prompts/tickets/`
- `prompts/codex_tickets_1_2.md` -> `prompts/tickets/`
- `prompts/codex_ticket_template.md` -> `prompts/tickets/`

### Move handoff packets
Move all files matching:
- `prompts/codex_handoff_*.md` -> `prompts/handoffs/`
- `prompts/codex_handoff_*_change_report.md` -> `prompts/handoffs/`

### Update runner template for new folder structure
Update `prompts/runners/codex_run_ticket.md`:

- It must reference the change report spec at:
  `prompts/runners/codex_change_report_prompt.md`

- Update input placeholder to accept a relative path, not just a filename:
  - Replace any <TICKET_FILENAME> logic with:
    **<TICKET_MD_PATH>**, which will be something like:
    `prompts/tickets/codex_ticket_36_38.md`

- Update the report save path rule to save next to the ticket:
  - If ticket path is `prompts/tickets/codex_ticket_39_40.md`
  - Then report path must be:
    `prompts/tickets/codex_ticket_39_40_change_report.md`

(If you need to define a simple rule in prose rather than compute paths, do so.)

### Update any references in tickets (if needed)
If any existing tickets in `prompts/tickets/` refer to old locations like `prompts/codex_change_report_prompt.md`,
update those references to the new runner path.

---

## Required commands
- `uv run pytest src/kymflow/core/zarr/tests -q`

No demo scripts required.

---

## Definition of Done
- `prompts/README.md` exists and explains workflow clearly.
- Runners live in `prompts/runners/`
- Tickets + change reports live in `prompts/tickets/`
- Handoffs live in `prompts/handoffs/`
- `prompts/runners/codex_run_ticket.md` works with ticket paths in new structure.
- Tests pass.

---

## Manual steps for the human (Robert)
None required. The reorg should be done entirely via this ticket using `git mv`.
