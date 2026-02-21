# filename: prompts/runners/codex_run_ticket.md

# Codex Unified Ticket Runner

You will implement a ticket AND generate its change report in one pass.

INPUT:
- Ticket markdown path (workspace-relative): <TICKET_MD_PATH>

WORKFLOW:

1) Read:
   <TICKET_MD_PATH>

2) Implement all tasks described in that ticket on the current branch.

   Implementation Rules:
   - Respect architectural boundaries.
   - Do not introduce broad `except Exception` unless immediately re-raised.
   - Public APIs must include:
       • type hints
       • Google-style docstrings
   - Preserve test stability.
   - Keep changes minimal and scoped to ticket goals.

   Docs Contract Rule (NEW):
   - The folder `src/kymflow/core/zarr/docs/` is a living API contract.
   - If your changes impact ANY of the following, you MUST update the docs in the same ticket:
       • public API surface (new/removed/renamed public functions/classes)
       • method signatures
       • read/write semantics
       • on-disk data layout
       • ingest/export workflows
       • exception behavior that callers depend on
   - At minimum, update `docs/api.md` and any relevant doc pages (workflows/layout/incremental).
   - If docs are not updated when required, treat the ticket as incomplete.

3) Run required commands:
   - At minimum:
       uv run pytest src/kymflow/core/zarr/tests -q
   - Also run any demo scripts referenced in the ticket.

4) If tests fail:
   - Fix implementation until tests pass.

5) Generate a strict change report following:
   prompts/runners/codex_change_report_prompt.md

6) Save the report as:
   Next to the ticket file path.
   - If ticket is `prompts/tickets/codex_ticket_39_40.md`
   - Save report as `prompts/tickets/codex_ticket_39_40_change_report.md`

7) In your final message include:
   - Path to saved change report
   - Commands executed and results
   - Docs updated? yes/no (list files changed under docs/ if yes, or state why not required)
   - Known limitations or TODOs introduced

Proceed.
