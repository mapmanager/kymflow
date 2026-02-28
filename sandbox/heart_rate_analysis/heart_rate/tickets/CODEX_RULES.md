# CODEX_RULES.md — Heart-rate sandbox ticket execution rules (GLOBAL)

These rules apply to **every** ticket in:

kymflow/sandbox/heart_rate_analysis/heart_rate/

Codex must follow these rules even if a ticket forgets to restate them.

## 1) Hard boundary (never violate)
Codex may ONLY edit files inside:

kymflow/sandbox/heart_rate_analysis/heart_rate/

If any requested change requires edits outside this folder, STOP and report that constraint.

## 2) Ticket is the source of truth for scope
Each ticket MUST contain a **Scope (STRICT)** section with:

- **Allowed edits**: explicit list of files Codex may edit
- **Forbidden edits**: explicit list of files Codex must not edit (optional but recommended)

Codex may ONLY modify files listed under **Allowed edits**.

## 3) No unrelated refactors
Do not:
- Reformat unrelated code
- Rename symbols unless required by the ticket
- Reorder imports unless required
- Change behavior outside what the ticket requests

## 4) No invented APIs
If the ticket asks for behavior but the API doesn't exist:
- Do NOT fabricate new APIs
- Implement a graceful fallback that keeps the code runnable
- Document the limitation clearly in the report

## 5) Preserve plotting function signature pattern
Do not remove the pattern:

`ax: Optional[plt.Axes] = None`

from existing plot function signatures unless a ticket explicitly allows it.

## 6) Domain constraint: ROI handling in CSV inputs
Many CSVs contain parallel measurements distinguished by a `roi_id` column.

**Never** compute heart-rate analysis across multiple `roi_id` values mixed together.

Rules:
- If a `roi_id` column exists, analysis MUST be performed on exactly ONE `roi_id` at a time.
- In this project, `roi_id` is REQUIRED for CSV-based HR analysis unless a ticket explicitly changes that rule.
- Tickets that add/modify CSV loading must:
  - require an explicit `roi_id` selection at analysis time, AND
  - ensure results are stored per-roi (never mixed).

## 7) Documentation + typing standard (required)
Unless a ticket explicitly opts out, all newly added or modified public-facing elements must include:

- Fully typed function signatures (including return types).
- Google-style docstrings documenting:
  - Inputs (types/units/shape expectations)
  - Computation/assumptions
  - Returns (types, meaning)
  - Failure/None cases and reasons
  - ROI semantics where applicable

**Docs output:** Codex should create/maintain documentation in:
- `kymflow/sandbox/heart_rate_analysis/heart_rate/docs/`

Docs may include:
- API references (module/class/function)
- “How to run” / end-user notes
- Interpretation/QC guidance

If a ticket changes behavior or adds new analysis outputs, update/create a corresponding doc in `docs/`.

## 8) Required report output (every ticket)
After implementing a ticket `<ticket_name>.md`, Codex MUST create:

kymflow/sandbox/heart_rate_analysis/heart_rate/tickets/<ticket_name>_codex_report.md

Example:
ticket_1.md -> ticket_1_codex_report.md

### Report MUST include (in this order)

1) **Modified code files**
   - List ONLY code files changed (e.g. .py, .md if explicitly allowed by ticket).
   - Do NOT count the report file itself here.

2) **Artifacts created/updated**
   - Include the report file:
     `tickets/<ticket_name>_codex_report.md`
   - Include any other non-code artifacts created by the process.

3) **Scope confirmation**
   - Explicitly confirm:
     a) No files outside `kymflow/sandbox/heart_rate_analysis/heart_rate/` were modified.
     b) No files outside the ticket’s **Allowed edits** list were modified.

4) **Unified diff (short)**
   - Provide a short unified diff for each modified code file.
   - If the diff is large, include:
     - The most relevant hunks, and
     - A brief summary of omitted hunks.

5) **Search confirmation**
   - State:
     “I searched for other occurrences of <pattern/bug> and did not change them.”
     OR list what was found and why it was or wasn’t modified.

6) **Validation (commands actually run)**
   - List the exact command(s) you executed (copy/paste), e.g.:
     - `uv run python run_heart_rate_examples_fixed2.py`
     - `uv run pytest -q`
   - If you did not run anything, say so explicitly and explain why.

7) **Expected validation markers**
   - State what successful output looks like:
     - key console lines to expect (markers), AND/OR
     - output files/figures produced, AND/OR
     - tests that should pass.

8) **Summary of changes**
   - Bullet list of behavioral changes.

9) **Risks / tradeoffs**
   - What could break, what assumptions changed.

10) **Self-critique**
   - Pros
   - Cons
   - Drift risk
   - Red flags / architectural violations (if any)

## 9) Validation + tests
Tickets should keep code runnable and increase test coverage over time.

Preferred commands:
- Run scripts:
  `uv run python <script.py> [args]`
- Run unit tests (located under `heart_rate/tests/`):
  `uv run pytest -q`

If tests are not present, or cannot be run, Codex must:
- Say so explicitly, and
- Provide clear manual validation commands.

## 10) Keep tickets runnable and diffs minimal
Codex should:
- Prefer minimal diffs
- Avoid broad refactors unless explicitly requested by the ticket
- Keep control flow clear and explicit
