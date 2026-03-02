We are working inside a strictly scoped engineering workflow.

All edits must be confined to:

kymflow/src/kymflow/core/analysis/heart_rate/

Inside that folder, there is a tickets/ directory containing:
- CODEX_RULES.md (global execution rules)
- TICKET_TEMPLATE.md
- Individual ticket files (ticket_X.md)

You must always:
1) Read and follow tickets/CODEX_RULES.md before executing any ticket.
2) Treat each ticket as the only allowed change scope.
3) Only edit files listed under “Allowed edits” in the ticket.
4) Never edit files outside heart_rate/.
5) Produce a report file named:
   tickets/<ticket_name>_codex_report.md
   following the report format in CODEX_RULES.md.

If a requested change requires editing outside the allowed scope,
you must STOP and explain why instead of making the change.

Acknowledge that you understand these constraints.