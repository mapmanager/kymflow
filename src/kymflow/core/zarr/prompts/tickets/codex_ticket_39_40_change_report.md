# Codex Ticket 39–40 Change Report

## 1) Branch name used
- `kymflow-zarr`

## 2) Commands run and exact outcomes
1. `git -C /Users/cudmore/Sites/kymflow_outer/kymflow rev-parse --abbrev-ref HEAD`
   - Outcome: `kymflow-zarr`
2. Initial move command using `git mv` + loops from `prompts/`
   - Outcome: partial success, then failed on untracked file with:
     - `fatal: not under version control, source=.../codex_ticket_39_40.md`
3. Recovery move commands:
   - `git mv codex_handoff_*.md handoffs/`
   - `mv codex_ticket_39_40.md tickets/codex_ticket_39_40.md`
   - Outcome: completed structure reorg.
4. `uv run pytest src/kymflow/core/zarr/tests -q`
   - Outcome: `33 passed`

## 3) Files modified (full relative paths) with per-file details

### Runner templates (moved and updated)
- `src/kymflow/core/zarr/prompts/codex_run_ticket.md` -> `src/kymflow/core/zarr/prompts/runners/codex_run_ticket.md`
  - What changed: path header updated; input placeholder changed from `<TICKET_FILENAME>` to `<TICKET_MD_PATH>`; change-report spec path updated to `prompts/runners/codex_change_report_prompt.md`; report save rule updated to "save next to ticket path".
  - Why: Ticket 40 requires runner to support ticket paths in new folder layout and correct report pathing.
  - Behavior vs refactor: **Behavior change** (workflow contract and invocation semantics changed).

- `src/kymflow/core/zarr/prompts/codex_implement_ticket_and_gen_report_prompt.md` -> `src/kymflow/core/zarr/prompts/runners/codex_implement_ticket_and_gen_report_prompt.md`
  - What changed: change-report spec path clarified to `prompts/runners/codex_change_report_prompt.md`.
  - Why: align moved runner assets.
  - Behavior vs refactor: **Behavior change** for runner instructions only.

- `src/kymflow/core/zarr/prompts/codex_change_report_prompt.md` -> `src/kymflow/core/zarr/prompts/runners/codex_change_report_prompt.md`
  - What changed: file relocated only.
  - Why: runner assets now centralized under `prompts/runners/`.
  - Behavior vs refactor: **Refactor-only** (location change).

### Prompt catalog files (moved)
- `src/kymflow/core/zarr/prompts/codex_ticket_07_10.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_07_10.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_07_10_change_report.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_07_10_change_report.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_11_13.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_11_13.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_11_13_change_report.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_11_13_change_report.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_14_17.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_14_17.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_14_17_change_report.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_14_17_change_report.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_18_21.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_18_21.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_18_21_change_report.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_18_21_change_report.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_22_25.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_22_25.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_22_25_change_report.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_22_25_change_report.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_26_29.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_26_29.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_26_29_change_report.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_26_29_change_report.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_30_32.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_30_32.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_30_32_change_report.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_30_32_change_report.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_33_35.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_33_35.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_33_35_change_report.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_33_35_change_report.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_36_38.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_36_38.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_36_38_change_report.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_36_38_change_report.md`
- `src/kymflow/core/zarr/prompts/codex_ticket_template.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_ticket_template.md`
- `src/kymflow/core/zarr/prompts/codex_tickets_1_2.md` -> `src/kymflow/core/zarr/prompts/tickets/codex_tickets_1_2.md`
  - What changed: files relocated to `prompts/tickets/`.
  - Why: Ticket 40 folder reorganization.
  - Behavior vs refactor: **Refactor-only** (storage location).

### Handoffs (moved)
- `src/kymflow/core/zarr/prompts/codex_handoff_kymdataset_indexers_v01.md` -> `src/kymflow/core/zarr/prompts/handoffs/codex_handoff_kymdataset_indexers_v01.md`
- `src/kymflow/core/zarr/prompts/codex_handoff_kymdataset_indexers_v01_change_report.md` -> `src/kymflow/core/zarr/prompts/handoffs/codex_handoff_kymdataset_indexers_v01_change_report.md`
- `src/kymflow/core/zarr/prompts/codex_handoff_tickets_3_6.md` -> `src/kymflow/core/zarr/prompts/handoffs/codex_handoff_tickets_3_6.md`
- `src/kymflow/core/zarr/prompts/codex_handoff_tickets_3_6_change_report.md` -> `src/kymflow/core/zarr/prompts/handoffs/codex_handoff_tickets_3_6_change_report.md`
  - What changed: files relocated to `prompts/handoffs/`; one historical report also had path string updates from old prompt locations.
  - Why: Ticket 40 folder reorganization + reference cleanup.
  - Behavior vs refactor: **Mostly refactor-only**; minor textual reference updates.

### Ticket reference updates
- `src/kymflow/core/zarr/prompts/tickets/codex_ticket_39_40.md`
  - What changed: updated during relocation; explicit move examples preserved (old -> new paths) and new-structure references retained.
  - Why: ticket file moved and normalized after global path updates.
  - Behavior vs refactor: **Refactor-only** (spec content maintenance).

## 4) Files added
- `src/kymflow/core/zarr/prompts/README.md`
  - Added prompts directory guide, subfolder purpose, standard workflow, and invocation pattern using `<TICKET_MD_PATH>`.
- `src/kymflow/core/zarr/prompts/tickets/codex_ticket_39_40.md`
  - Added ticket file in new `tickets/` location (source file was untracked before move).
- `src/kymflow/core/zarr/prompts/archive/` (directory)
  - Added as fourth documented subfolder to satisfy README structure requirement.

## 5) Files deleted
- None.
- Note: many prompt files were moved (git renames), not deleted.

## 6) Public API changes (functions/methods/signatures)
- No runtime Python API changes.
- Prompt-runner interface changed:
  - `codex_run_ticket.md` input contract changed from `<TICKET_FILENAME>` to `<TICKET_MD_PATH>`.
  - Change-report spec path changed to `prompts/runners/codex_change_report_prompt.md`.
  - Report save path rule changed to "next to ticket".

## 7) Exception handling changes
- None in code/runtime.
- Workflow text unchanged regarding exception style rules.

## 8) Read/write semantics changes
- No zarr data read/write semantics changes.
- Prompt workflow semantics changed: report output location now follows ticket path location.

## 9) Data layout changes
- Prompt file layout changed under `src/kymflow/core/zarr/prompts/`:
  - `runners/` now holds runner templates/specs.
  - `tickets/` now holds ticket specs and change reports.
  - `handoffs/` now holds handoff docs and reports.
  - `archive/` added for optional retired/superseded prompt assets.

## 10) Known limitations / TODOs
- `archive/` is currently empty; usage policy is documented but not yet exercised.
- Historical change-report markdown paths were text-updated where encountered; additional historical path references may still exist in older narrative sections and are non-functional metadata only.
