# CODEX_RULES.md

These are the **hard rules** for the Executor LLM (Codex). They apply to every ticket.

## 0) Read-first
Before editing anything:
1) Read the ticket file completely.
2) Read this CODEX_RULES.md.
3) Confirm the allowed scope and constraints.

## 1) Scope constraints (HARD)
- Only edit files explicitly allowed by the ticket.
- Do not modify files outside scope.
- If a change outside scope is required, stop and follow `ESCALATION_PROTOCOL.md`.

## 2) No guessing
- If a requirement is ambiguous, stop and ask (via report) rather than invent behavior.
- Do not invent new APIs unless the ticket explicitly requests it.

## 3) Report required (HARD)
For every ticket, create an implementation report.

### 3.1 Derive report name from ticket filename (HARD)
- Let the ticket file be: `tickets/<ticket_file>.md` (basename without extension = `<ticket_file>`).
- Default report path MUST be: `tickets/<ticket_file>_codex_report.md`
  - Example: ticket `ticket_002_hardened.md` -> report `ticket_002_hardened_codex_report.md`.
- If that report path already exists, DO NOT overwrite it.
  - Write `tickets/<ticket_file>_codex_report_v2.md`, or `..._v3.md`, `..._v4.md`, etc. until you find an unused path.
- Report content MUST include the final report path that was written.

### 3.2 Never overwrite a real report (HARD)
- Never overwrite an existing non-empty report file.
- If the target report exists but is **0 bytes**, it is considered a **partial/failed write**:
  - You MAY reuse/overwrite that 0-byte file, OR delete it and write the base report path.
  - If you choose not to reuse it, then write `_v2` as usual.

### 3.3 Atomic write rule (HARD)
To prevent 0-byte partial reports:
- Always write the report to a temporary file first, then rename to the final path.
- Procedure:
  1) Determine final report path per 3.1/3.2 (base or `_vN`).
  2) Write to: `<final_report_path>.tmp`
  3) Verify the tmp file is non-empty (size > 0) and appears to be valid Markdown text.
  4) Rename/move the tmp file to the final report path **atomically** (same folder).
  5) If rename fails, stop and report the failure (do not silently continue).

Operator notes:
- If you rename a ticket file, the report name changes accordingly.
- Do not copy/paste report paths into tickets; rely on these rules.
- If you see a leftover 0-byte base report, it is safe to delete; `_v2` (or higher) is authoritative.

### Report content MUST include
#### A) Modified code files
List only code files edited (exclude the report file itself).

#### B) Artifacts created
List report files and any non-code artifacts (docs, generated files).

#### C) Unified diff
Paste a short unified diff for each code file edited.
Prefer `git diff --unified=3` if available.

#### D) Search confirmation
State what you searched for (patterns) and whether you changed other occurrences.

#### E) Validation commands run
List exact commands you ran and their outcomes.
Examples:
- `uv run pytest -q`
- `uv run python run_example.py`

#### F) Summary of changes
Short bullet list.

#### G) Risks / tradeoffs
What could break? What was not tested?

#### H) Self-critique
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

## 7) Frontend/backend separation guardrail
- Backend logic (analysis, IO, filtering) must live outside `gui/`.
- `gui/` may call backend APIs but must not reimplement analysis logic.
- Do not reimplement analysis in views/widgets.
- Controller mediates state updates between GUI and backend.

## 8) File picker guardrail
- Do not modify `gui/file_picker.py` unless explicitly requested by the ticket.
- If modification is explicitly requested:
  - Must use `webview.FileDialog.OPEN`.
  - Must not use legacy `webview.OPEN_DIALOG`.
  - Must confirm dialog works in macOS native mode during validation.
  - Must include a manual smoke-test note in the report:
    - "Open TIFF dialog works in macOS native mode."

## 9) Views regression guardrail
- If a ticket modifies `gui/views.py`, acceptance criteria must include:
  - "Post Filter Params card must remain present and functional."
- When `gui/views.py` is modified, the report must explicitly confirm this card remains present and functional.

## 10) Real kymograph facade guardrail
- When dealing with real kymographs, use only `kymflow.core.api.kym_external` facade functions.
- Do not access `KymImage` convenience properties directly from diameter-analysis code.
