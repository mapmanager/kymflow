# ticket_019_boundary_test_and_fail_fast_adapter.md

## Goal

Lock in the “controller-only kymflow” boundary and make the adapter **fail fast** if the kymflow list contract is violated.

This ticket is intentionally **small and stabilizing**: boundary enforcement + one adapter robustness improvement. No ROI/channel logic refactors beyond what already exists.

---

## Scope

### A) Boundary enforcement test (practical)

Add/adjust a test that enforces:

- **Only** `diameter-analysis/gui/diameter_kymflow_adapter.py` may import from:
  - `kymflow.core.api.kym_external`
- **No other** `.py` file under `sandbox/diameter-analysis/` may import that module.

**Important**: Use a *practical* check: detect **actual import statements**, not mere text mentions in comments/docstrings.

#### Accepted import patterns (adapter only)
- `from kymflow.core.api.kym_external import ...`
- `import kymflow.core.api.kym_external`
- `import kymflow.core.api.kym_external as ...`

#### Test behavior
- Recursively scan `sandbox/diameter-analysis/` for `*.py`
- Exclude:
  - `__pycache__/`
  - `.venv/` (if present)
  - `tests/` **only if** you prefer tests to be allowed to reference kymflow; otherwise include tests too.
- For each file **except** `gui/diameter_kymflow_adapter.py`, fail if it contains an **import statement** matching the patterns above.

Implementation suggestion:
- Use a regex anchored to line-start with optional whitespace, e.g.
  - `^\s*from\s+kymflow\.core\.api\.kym_external\s+import\s+`
  - `^\s*import\s+kymflow\.core\.api\.kym_external(\s+as\s+\w+)?\s*$`
- Parse file as text; do not attempt AST parsing unless you want extra rigor.

---

### B) Adapter: fail fast contract for file-table listing

Refactor `list_file_table_kym_images(klist)` in `gui/diameter_kymflow_adapter.py`:

- **Do not** fall back to `list(klist)` or other “duck typing”.
- Treat the adapter contract as:
  - `klist` must be a kymflow list-like object exposing an `images` attribute that is iterable.

#### Required behavior
- If `klist is None`: return `[]` (keep).
- If `klist` lacks `.images`: raise `TypeError` with a clear message like:
  - `"Expected klist with .images (KymImageList contract); got <type>"`
- Otherwise: `return list(klist.images)`.

This aligns with: “trust kymflow API” and fail fast if the contract changes/breaks.

---

## Acceptance criteria

1. Tests pass.
2. Boundary test fails if any non-adapter file imports `kymflow.core.api.kym_external`.
3. Boundary test does **not** fail on mentions in comments/docstrings.
4. `list_file_table_kym_images` fails fast if `.images` is missing (TypeError), and still works for the normal kymflow list object.
5. No changes to `kymflow/` sources.

---

## Notes / Guardrails for Codex

- Do **not** modify anything under `kymflow/`.
- Do **not** reintroduce direct `kymflow.core.api.kym_external` imports outside `gui/diameter_kymflow_adapter.py`.
- Keep changes minimal and localized to:
  - boundary test file
  - `gui/diameter_kymflow_adapter.py` (fail-fast change)

