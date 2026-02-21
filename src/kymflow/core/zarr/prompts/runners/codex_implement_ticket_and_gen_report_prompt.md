# Codex Implement Ticket + Generate Change Report (One-Step)

You will do BOTH:
(A) implement the ticket, and
(B) generate + save a strict change report.

Inputs:
- Ticket file path: <TICKET_MD_PATH>
- Change report spec: prompts/runners/codex_change_report_prompt.md

Steps:
1) Read and understand <TICKET_MD_PATH>.
2) Implement all tickets in that file on the current git branch.
   - Follow architectural boundaries in the ticket.
   - Prefer targeted exceptions; do not introduce broad `except Exception` unless immediately re-raised.
   - Keep typed signatures and Google-style docstrings for new/changed public APIs.
   - If public API/read-write semantics/on-disk layout/exception behavior changes, update docs under `src/kymflow/core/zarr/docs/` in the same ticket (at minimum `docs/api.md` + relevant pages).
3) Run the required commands listed in the ticket (at minimum: the relevant pytest command; run any demo scripts explicitly requested).
4) If tests fail, fix until they pass.
5) Generate a change report that EXACTLY follows the format/sections in codex_change_report_prompt.md.
   (Use `prompts/runners/codex_change_report_prompt.md`.)
6) Save the report as:
   - <ticket_basename>_change_report.md
   - In the same directory as the ticket file, unless the repo already has a standard prompts/reports directory.
7) In your final response, include:
   - The path to the saved change report
   - The commands run and their outcomes (brief)
   - Docs updated? yes/no (list docs files changed if yes)
   - Any known limitations/TODOs

Now proceed using:
- Ticket: <TICKET_MD_PATH>
