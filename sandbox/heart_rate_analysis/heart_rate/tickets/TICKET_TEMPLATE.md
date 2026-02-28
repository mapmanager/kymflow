# TICKET_TEMPLATE.md — Heart Rate Sandbox Ticket Template

This template defines the REQUIRED structure for all tickets executed by Codex inside:

kymflow/sandbox/heart_rate_analysis/heart_rate/

**GLOBAL EXECUTION RULES live in:**
- kymflow/sandbox/heart_rate_analysis/heart_rate/tickets/CODEX_RULES.md

All tickets MUST follow this structure exactly.

---------------------------------------------------------------------
TICKET STRUCTURE
---------------------------------------------------------------------

# <ticket_name>.md — <Short Title>

## Context
Describe the problem clearly.

## Scope (STRICT)

### Allowed edits
- file_1.py
- file_2.py

### Forbidden edits
- List any files that must NOT be modified (optional but recommended).

## Requirements
List numbered requirements (R1, R2, R3…)
Be explicit about behavior changes.

## Acceptance Criteria
List testable outcomes.

## Notes
Optional clarifications.

---------------------------------------------------------------------
HOW TO INVOKE CODEX (MINIMAL PROMPT)
---------------------------------------------------------------------

Use this prompt (edit only the ticket path):

    Implement ticket:
    kymflow/sandbox/heart_rate_analysis/heart_rate/tickets/<ticket_name>.md

Codex must then read and follow:
- tickets/CODEX_RULES.md (global rules)
- the ticket itself (scope + requirements)

