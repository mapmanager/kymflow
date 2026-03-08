# Ticket 020 — AST-based kymflow boundary test (robust import detection)

## Context
We enforce a strict architectural boundary in `sandbox/diameter-analysis/`:

- Only `gui/diameter_kymflow_adapter.py` may import from `kymflow.core.api.kym_external`
- All other diameter-analysis modules must NOT import from that facade (controller/view/model/etc must go through the adapter)

Ticket 019 implemented a *practical* boundary test using regex scanning of source text. This works for common import styles but can miss unusual formatting (e.g., multiline imports).

This ticket hardens the boundary test by switching detection to AST parsing so we catch imports regardless of formatting.

## Goals
1. Replace regex-based import detection with AST-based detection in the boundary test.
2. Keep the same allowlist: `gui/diameter_kymflow_adapter.py` is allowed to import `kymflow.core.api.kym_external`; all other files are forbidden.
3. Keep the “practical” semantics: detect **real import statements only** (ignore comments/docstrings/strings).
4. Maintain current exclusions (e.g., ignore `.venv/`, `__pycache__/`, `tickets/`).

## Non-goals
- No refactors of application code.
- No changes under `kymflow/`.

## Implementation details
### A) Update boundary test to use AST
Target: `sandbox/diameter-analysis/tests/test_kymflow_boundary.py`

Replace the current regex matching with AST parsing:
- Parse each `.py` file with `ast.parse(source, filename=...)`
- Walk nodes and detect imports:
  - `ast.Import`: find aliases where `name == "kymflow.core.api.kym_external"`
  - `ast.ImportFrom`: find nodes where `module == "kymflow.core.api.kym_external"`
- Record violations for any file *not in allowlist*.

Important:
- Handle `SyntaxError` gracefully: fail the test with a helpful message that includes the file path.
- Keep the error output actionable:
  - Show the violating file path(s)
  - For each violating file, show the import statement location (line number) if feasible.

### B) Keep allowlist and file discovery behavior consistent
- Root: `sandbox/diameter-analysis/`
- Scan all `.py` files under the root, excluding:
  - `.venv/`, `__pycache__/`, `.pytest_cache/`, `dist/`, `build/`
  - `tickets/` (and any other ticket/report folders you currently exclude)
- Allowlist (relative path): `gui/diameter_kymflow_adapter.py`

### C) Verify
- `uv run pytest -q` passes.
- Confirm that:
  - Multiline imports are detected, e.g.
    - `from kymflow.core.api.kym_external import (\n    load_kym_list,\n    get_kym_by_path,\n)`
  - Aliased imports are detected:
    - `import kymflow.core.api.kym_external as ke`

## Acceptance criteria
- Boundary test fails if any non-allowlisted module imports `kymflow.core.api.kym_external`, regardless of import formatting.
- Boundary test ignores mentions in docstrings/comments.
- Test output clearly identifies violating files (and ideally line numbers).
- All tests pass.

## Codex guardrails
- Do not modify any files under `kymflow/`.
- Do not weaken the boundary rule.
- Do not reintroduce regex matching; AST parsing is required.
