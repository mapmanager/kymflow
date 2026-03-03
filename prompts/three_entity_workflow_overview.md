# Diameter Analysis Sandbox: 3‑Entity Development System (Human ↔ ChatGPT ↔ Codex)

This document describes the workflow we’re using in `kymflow/sandbox/diameter-analysis/` to develop a kymograph diameter analysis pipeline with a scoped, ticket-driven process.

---

## 1) The three entities and their roles

### Human (You)
**Primary role:** product owner + scientific domain expert + final integrator.

You:
- define requirements and priorities (algorithm, QC, UI behavior),
- decide what “correct” looks like by inspecting plots and outputs,
- run code locally (via `uv`), reproduce errors, and provide ground truth via visual inspection,
- approve/iterate on tickets and accept/reject Codex changes.

**Superpower:** knowing what’s scientifically meaningful and what tradeoffs are acceptable.

---

### ChatGPT (Architect LLM)
**Primary role:** system architect + spec writer + reviewer.

ChatGPT:
- translates your intent into concrete, testable tickets,
- designs API boundaries (backend vs GUI, dataclass schemas, file formats),
- maintains continuity across tickets and avoids architectural drift,
- reviews Codex reports and plans next steps,
- helps debug when appropriate, but ideally pushes implementation through tickets.

**Superpower:** keeping the “big picture” consistent while turning it into actionable work.

---

### Codex (Implementation LLM)
**Primary role:** fast implementer + test writer.

Codex:
- executes a ticket inside the repository/folder structure,
- writes/edits code, tests, docs, and reports what changed,
- follows rules for report naming, atomic writes, etc.

**Superpower:** quickly producing working code and tests from a specific spec.

---

## 2) What this workflow is optimizing for

This system is designed for projects where:
- requirements evolve (algorithm R&D),
- correctness depends on iterative visualization and domain judgment,
- there’s a strong need to avoid “LLM drift” (random refactors / brittle changes),
- you want reproducibility (tickets, reports, versioning, rollback).

The goal is **controlled acceleration**:
- Codex speeds up implementation,
- ChatGPT reduces ambiguity and enforces system integrity,
- Human validation prevents subtle scientific errors.

---

## 3) Architecture: how the workflow is implemented

### 3.1 Ticket files as the unit of work
Tickets are stored under `diameter-analysis/tickets/` and follow a standard template.  
Each ticket:
- has a goal,
- defines scope/constraints,
- lists deliverables and acceptance criteria,
- includes test requirements and run instructions.

**Why it matters:** tickets convert “ideas” into “verifiable changes.”

---

### 3.2 Codex report files as the unit of accountability
Every ticket run produces a report file:
- `tickets/<ticket_name>_codex_report.md` (or `_v2`, `_v3`, ...)

Reports are required to:
- list files changed/added,
- describe how to run tests and demos,
- document deviations from ticket scope.

**Key governance rule:** never overwrite a previous report; use version suffixes and atomic write.

---

### 3.3 Governance + safety rails
The system includes:
- **CODEX_RULES.md**: behavior constraints for Codex (scope, naming, report writing, no overwrites).
- **TICKET_TEMPLATE.md**: ensures every ticket contains the minimum necessary structure.
- **Architecture snapshots**: keep the global shape stable as the system evolves.
- **Rollback strategy**: enables reverting without losing history.

These rails are what prevent “LLM refactor roulette.”

---

## 4) Execution loop: the canonical iteration cycle

### Step 0: Human defines intent / problem
You provide:
- goals (e.g., “add gradient-based edge detection”),
- constraints (parallel-first, plotting conventions, transpose rule),
- examples (synthetic presets, known failure modes).

### Step 1: ChatGPT drafts or hardens a ticket
ChatGPT:
- clarifies missing requirements (only when necessary),
- writes a ticket with concrete acceptance criteria,
- ensures scope is tight and integrates with existing architecture.

### Step 2: Codex processes the ticket
Codex:
- implements changes,
- adds/updates tests and docs,
- writes a report file with versioned naming.

### Step 3: Human runs code locally and validates
You:
- run `uv run ...` scripts / NiceGUI app,
- inspect plots / overlays / QC behavior,
- report bugs or desired improvements.

### Step 4: ChatGPT reviews report + results and plans next ticket
ChatGPT:
- reads Codex report (and your feedback),
- proposes next steps and drafts the next ticket.

Repeat until stable.

---

## 5) Why this system works well for scientific image analysis R&D

Kymograph diameter detection is a classic “interactive algorithm development” problem:
- multiple candidate methods,
- no labeled ground truth,
- correctness judged by overlays and time series plausibility,
- QC and failure mode detection are as important as the number.

This workflow supports that by:
- allowing fast iteration (Codex),
- maintaining consistent interfaces (ChatGPT),
- ensuring scientific judgment stays human-controlled.

---

## 6) Pros and cons vs other development systems

### 6.1 Pros
**Strong reproducibility**
- Tickets + reports create an audit trail of decisions and changes.

**Reduced context loss**
- ChatGPT maintains continuity between tickets and prevents architectural fragmentation.

**High velocity with guardrails**
- Codex implements quickly but is constrained by scope rules and acceptance criteria.

**Scales to multiple subprojects**
- The same workflow works for backend algorithm, synthetic data generation, UI, file formats, etc.

**Encourages good engineering**
- Tests, modular design, and documented APIs become “default.”

---

### 6.2 Cons / failure modes
**Overhead**
- Writing tickets adds friction vs “just hacking.”

**Spec mismatch risk**
- If a ticket is underspecified, Codex will guess; that creates churn.

**Tool limitations**
- Some interactive UIs (e.g., notebooks) can be brittle; better to use a fully controlled GUI framework.

**Refactor temptation**
- Codex may attempt “helpful refactors” unless the rules explicitly forbid them.

---

## 7) Comparison to alternatives

### A) Pure human coding (no LLM)
- ✅ Max control, minimal process overhead
- ❌ Slower iteration, harder to maintain parallel explorations

### B) ChatGPT “direct coding in chat” (no tickets)
- ✅ Fast to get snippets
- ❌ Low reproducibility, easy to lose structure, difficult to manage multi-file changes

### C) Codex “direct coding” (no architect layer)
- ✅ Fast implementation
- ❌ Much higher risk of architectural drift and incorrect assumptions

### D) Classic Jira + human-only implementation
- ✅ Strong tracking and accountability
- ❌ Too slow/expensive for exploratory algorithm R&D

**This system sits between B and D**:
- more structured than ad-hoc chat coding,
- lighter-weight than full project management tooling.

---

## 8) Best practices (what keeps this system healthy)

### Ticket authoring
- Keep scope tight (one major feature per ticket).
- Include acceptance criteria that a human can check quickly.
- Call out invariants explicitly (e.g., transpose convention, ROI semantics).

### Codex interaction
- Require report + tests for every ticket.
- Enforce “do not re-architect” unless ticket says so.
- Enforce atomic write + never overwrite reports.

### Human validation
- Always validate with plots/overlays before moving on.
- Record good synthetic presets and edge cases.
- Prefer adding QC metrics early, not as an afterthought.

---

## 9) Where we are now (conceptually)
We have:
- a backend diameter-analysis pipeline (methods, params, results),
- a synthetic kymograph generator for stress testing,
- a NiceGUI front-end for interactive exploration,
- a ticket system to evolve all of it safely.

The next phase is typically:
- file IO integration (TIFF loader),
- batch processing,
- algorithm tuning + QC strengthening,
- export/serialization stability.

---

## 10) Summary
This 3‑entity system is a pragmatic framework for moving quickly *without* losing control:
- Human keeps scientific truth and product direction.
- ChatGPT keeps architecture consistent and converts intent into verified work.
- Codex turns tickets into code efficiently, with tests and audit trails.

