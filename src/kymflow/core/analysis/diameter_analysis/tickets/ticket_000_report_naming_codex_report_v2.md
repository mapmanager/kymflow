# ticket_000_report_naming implementation report

Final report path written:
- `kymflow/sandbox/diameter-analysis/tickets/ticket_000_report_naming_codex_report_v2.md`

## Summary of changes
- Added deterministic ticket-filename-derived report naming and hard no-overwrite behavior in `CODEX_RULES.md`.
- Updated `TICKET_TEMPLATE.md` report section to explicitly require filename-derived naming and `_v2+` suffixing when needed.
- Added operator reminders in `CODEX_RULES.md` about ticket renaming impact and avoiding hardcoded report paths.

## A) Modified code files
- None.

## B) Artifacts created
- `kymflow/sandbox/diameter-analysis/tickets/ticket_000_report_naming_codex_report_v2.md`

## File-by-file list of changes
- `kymflow/sandbox/diameter-analysis/tickets/CODEX_RULES.md`
  - Added hard report filename rule using `<ticket_file>` basename.
  - Added hard no-overwrite `_v2/_v3/...` rule.
  - Added requirement that report content includes final path written.
  - Added operator notes (rename-ticket => rename-report, no path copy/paste).
- `kymflow/sandbox/diameter-analysis/tickets/TICKET_TEMPLATE.md`
  - Replaced ambiguous `tickets/<ticket_name>_codex_report.md` with explicit ticket-filename-derived instructions and no-overwrite suffixing.

## C) Unified diff (short)
### `kymflow/sandbox/diameter-analysis/tickets/CODEX_RULES.md`
```diff
@@
 ## 3) Report required (HARD)
 For every ticket, create:
-- `tickets/<ticket_name>_codex_report.md`
+- Let the ticket file be: `tickets/<ticket_file>.md` (basename without extension = `<ticket_file>`).
+- Default report path MUST be: `tickets/<ticket_file>_codex_report.md`
+  - Example: ticket `ticket_002_hardened.md` -> report `ticket_002_hardened_codex_report.md`.
+- If that report path already exists, DO NOT overwrite it.
+  - Write `tickets/<ticket_file>_codex_report_v2.md`, or `..._v3.md`, `..._v4.md`, etc. until unused.
+- Report content MUST include the final report path that was written.
+
+Operator notes:
+- If you rename a ticket file, the report name changes accordingly.
+- Do not copy/paste report paths into tickets; rely on this rule.
```

### `kymflow/sandbox/diameter-analysis/tickets/TICKET_TEMPLATE.md`
```diff
@@
 ## Codex implementation report
-Save:
-- `tickets/<ticket_name>_codex_report.md`
+Save report as:
+- `tickets/<this_ticket_filename_without_.md>_codex_report.md`
+If that file exists, save as:
+- `tickets/<this_ticket_filename_without_.md>_codex_report_v2.md` (or higher)
+Never overwrite an existing report.
```

## D) Search confirmation
Searched in `kymflow/sandbox/diameter-analysis/tickets/*.md` for:
- `tickets/<ticket_name>_codex_report.md`
- `codex_report_v2`
- `ticket_002_hardened.*codex_report`

Result:
- No remaining ambiguous template guidance in `CODEX_RULES.md` or `TICKET_TEMPLATE.md`.
- Updated guidance consistently uses ticket-filename-derived naming with no-overwrite suffixing.

## E) Validation commands run
- `uv run python -c "from pathlib import Path; import re; p=Path('kymflow/sandbox/diameter-analysis/tickets'); txt='\n'.join(x.read_text(encoding='utf-8') for x in p.glob('*.md')); assert 'codex_report_v2' in txt; assert re.search(r'ticket_002_hardened.*codex_report', txt, flags=re.I)"`
  - Passed (exit code 0).
  - Note: uv emitted one non-fatal warning about unrelated metadata read in another local path.

## F) Summary of changes
- Hardened report naming rule in governance.
- Added mandatory no-overwrite rule with version suffix fallback.
- Clarified template/report instructions to avoid ambiguity.

## G) Risks / tradeoffs
- `CODEX_RULES.md` is currently an untracked file in this repo state (pre-existing workspace condition), so downstream consumers must ensure this file is actually adopted in source control.
- Existing historical tickets may still contain old examples in their own text; governance/template now enforce the new rule.

## H) Self-critique
- Pros: Implements exact naming/no-overwrite policy and validates required markers.
- Cons: Validation checks string presence rather than fully parsing semantics.
- Drift risk: low, provided new tickets continue to use updated template.

## Scope confirmation
No files outside `kymflow/sandbox/diameter-analysis/tickets/` were modified.
