# Codex Unified Ticket Runner

You will implement a ticket AND generate its change report in one pass.

INPUT:
- Ticket filename (relative to prompts/ folder): <TICKET_FILENAME>

WORKFLOW:

1. Read:
   prompts/<TICKET_FILENAME>

2. Implement all tasks described in that ticket on the current branch.

   Implementation Rules:
   - Respect architectural boundaries.
   - Do not introduce broad `except Exception` unless immediately re-raised.
   - Public APIs must include:
       • type hints
       • Google-style docstrings
   - Preserve test stability.
   - Keep changes minimal and scoped to ticket goals.

3. Run required commands:
   - At minimum:
       uv run pytest src/kymflow/core/zarr/tests -q
   - Also run any demo scripts referenced in the ticket.

4. If tests fail:
   - Fix implementation until tests pass.

5. Generate a strict change report following:
   prompts/codex_change_report_prompt.md

6. Save the report as:
   prompts/<TICKET_FILENAME_without_.md>_change_report.md

7. In your final message include:
   - Path to saved change report
   - Commands executed and results
   - Known limitations or TODOs introduced

Proceed.