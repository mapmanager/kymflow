# CODEX_RULES.md (Template)

These are the **hard rules** for the Executor LLM (Codex). They apply to every ticket.

## 0) Read-first
Before editing anything:
1) Read the ticket file completely.
2) Read this CODEX_RULES.md.
3) Confirm the allowed scope and constraints.

## 1) Scope constraints (HARD)
- Only edit files explicitly allowed by the ticket.
- Do not modify files outside scope.
- If a change outside scope is required, stop and follow ESCALATION_PROTOCOL.md.

## 2) No guessing
- If a requirement is ambiguous, stop and ask (via report) rather than invent behavior.
- Do not invent new APIs unless the ticket explicitly requests it.

## 3) Report required (HARD)
For every ticket, create:
- Let the ticket file be: `tickets/<ticket_file>.md` (basename without extension = `<ticket_file>`).
- Default report path MUST be: `tickets/<ticket_file>_codex_report.md`
  - Example: ticket `ticket_002_hardened.md` -> report `ticket_002_hardened_codex_report.md`.
- If that report path already exists, DO NOT overwrite it.
  - Write `tickets/<ticket_file>_codex_report_v2.md`, or `..._v3.md`, `..._v4.md`, etc. until unused.
- Report content MUST include the final report path that was written.

Operator notes:
- If you rename a ticket file, the report name changes accordingly.
- Do not copy/paste report paths into tickets; rely on this rule.

The report must include:

### A) Modified code files
List only code files edited (exclude the report file itself).

### B) Artifacts created
List report files and any non-code artifacts (docs, generated files).

### C) Unified diff
Paste a short unified diff for each code file edited.
Prefer `git diff --unified=3` if available.

### D) Search confirmation
State what you searched for (patterns) and whether you changed other occurrences.

### E) Validation commands run
List exact commands you ran and their outcomes.
Examples:
- `uv run pytest -q`
- `uv run python run_example.py`

### F) Summary of changes
Short bullet list.

### G) Risks / tradeoffs
What could break? What was not tested?

### H) Self-critique
Pros/cons, drift risk, red flags, and what you’d do differently.

## 4) Tests and docs
- Prefer adding tests for bug fixes or schema changes.
- Place tests under `tests/` and run with `uv run pytest -q` if applicable.
- Add/update docs under `docs/` when APIs or schemas change.

## 5) Platform notes
- macOS multiprocessing requires `if __name__ == "__main__":` guard.
- Keep example scripts thin; prefer calling library APIs.

## 6) Completion criteria
Do not claim completion unless:
- All acceptance criteria pass
- Validation commands were run successfully
