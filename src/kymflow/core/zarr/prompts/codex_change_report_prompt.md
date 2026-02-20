# Codex Change Report Prompt

Produce a strict technical implementation report with:

1. Branch name used
2. Commands run and exact outcomes
3. Files modified (full relative paths) with per-file:
   - what changed
   - why
   - behavior change vs refactor-only
4. Files added
5. Files deleted
6. Public API changes (functions/methods/signatures)
7. Exception handling changes
8. Read/write semantics changes
9. Data layout changes
10. Known limitations / TODOs

Constraints:
- Be concrete and exhaustive.
- Include semantic changes and edge cases.
- Do not provide a high-level-only summary.
