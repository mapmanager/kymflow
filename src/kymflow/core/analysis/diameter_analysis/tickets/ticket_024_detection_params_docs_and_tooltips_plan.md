# Ticket 024 — Detection Params Docs + Docstrings + GUI Tooltips Plan

**Goal:** Improve understanding, tuning, and future maintainability of diameter detection by documenting *exactly* what each detection parameter does, which detection method uses it, and how users should tune it. Lay groundwork for GUI tooltips sourced from a single canonical description field.

**Status/Context**
- Current GUI exposes `DiameterDetectionParams` via `dataclass_editor_card`.
- Users need practical guidance to reduce artifacts (e.g., centerline/edges “jumping” on low-quality kymographs).
- We want a single source of truth for parameter meanings (docs + docstrings now; GUI tooltips next).

---

## Scope

### 1) Add docs page for detection parameters
**Add file:** `docs/detection_params.md` (or your existing docs folder convention).

Must include:
- Short overview of detection pipeline and where params apply.
- A **parameter-by-parameter reference**:
  - **Name**
  - **Type**
  - **Default**
  - **Units** (explicit: px, µm, seconds, dimensionless)
  - **Valid range / constraints** (if known)
  - **Which method(s) use it** (`threshold_width`, `gradient_edges`, etc.)
  - **Effect of increasing/decreasing** (heuristics)
  - **Common failure modes** and which params to adjust (e.g., “edges jump”, “centerline unstable”, “false edges”)

Also include a **Tuning cookbook** section:
- “Edges jump frame-to-frame”
- “Edges stick to noise texture”
- “Threshold method underestimates width”
- “Gradient method picks inner edge instead of wall”
- “Low SNR / faint edges”

### 2) Update Google-style docstrings (source of truth in code)
Update docstrings for:
- `DiameterDetectionParams` (Google style: Args/Attributes with per-field descriptions).
- Detection method functions/classes that consume params:
  - Explicitly list which params are read by each method.
  - If some params are ignored depending on `diameter_method`/mode, say so.

**Acceptance criteria**
- Every field in `DiameterDetectionParams` has a clear description in docstrings.
- Docstrings explicitly state units and method applicability.
- No stale/incorrect parameter names.

### 3) Tooltips plan for GUI (decision + minimal wiring)
We want a single canonical place for descriptions that GUI can use.

**Decision required (do this in this ticket):**
Choose one:
- **A (recommended):** `dataclasses.field(metadata={"description": "..." , "units": "...", "method": "...", ...})`
- B: separate schema dict mapping `field_name -> {description, units, ...}`
- C: parse docstrings (not recommended)

**Implement minimal wiring (optional but preferred if easy):**
- Extend `dataclass_editor_card` so each field can display help text.
- At minimum: show a small help label under each control (or tooltip icon) using metadata `description`.

**Guardrails**
- Do NOT duplicate descriptions in multiple places long-term.
- Keep UI change minimal; no redesign.

---

## Non-goals (explicitly out of scope)
- Refactoring detection algorithm behavior.
- Adding new detection modes.
- Motion-constraint changes (covered by ticket_014 and follow-ups).
- Serialization schema changes (ticket_022 series).

---

## Acceptance Tests / Checks
- Docs file renders and is readable.
- Grep check: every `DiameterDetectionParams` field name appears in docs file.
- GUI still runs; detection params card still renders.
- If tooltips wiring implemented: at least one field displays its description from metadata.

---

## Notes for Codex
- Do not modify anything under `kymflow/` (external dependency contract).
- Keep changes inside `sandbox/diameter-analysis/`.
- Avoid “brittle” hardcoded to_row/from_row style mapping when not needed (ticket_022 focus).
