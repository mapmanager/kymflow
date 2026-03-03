# Ticket 020 Codex Report

Final report path written: `sandbox/diameter-analysis/tickets/ticket_020_ast_boundary_test_codex_report.md`

## Summary of changes
- Replaced regex/text boundary detection with AST-based import detection in `tests/test_kymflow_boundary.py`.
- Kept same boundary semantics: only `gui/diameter_kymflow_adapter.py` may import `kymflow.core.api.kym_external`.
- Added robust exclusions and syntax-error handling with actionable failure messages.

## A) Modified code files
- `sandbox/diameter-analysis/tests/test_kymflow_boundary.py`

## B) Artifacts created
- `sandbox/diameter-analysis/tickets/ticket_020_ast_boundary_test_codex_report.md`

## C) Unified diff

### `sandbox/diameter-analysis/tests/test_kymflow_boundary.py`
```diff
@@
+import ast
@@
-GUI_DIR = Path(__file__).resolve().parents[1] / "gui"
+ROOT = Path(__file__).resolve().parents[1]
+ALLOWED = ROOT / "gui" / "diameter_kymflow_adapter.py"
+EXCLUDED_DIRS = {"__pycache__", ".venv", ".pytest_cache", "dist", "build", "tickets"}
+TARGET_MODULE = "kymflow.core.api.kym_external"
@@
-def test_only_adapter_imports_kym_external() -> None:
-    hits: list[str] = []
-    for p in GUI_DIR.glob("*.py"):
-        text = p.read_text(encoding="utf-8")
-        if "kymflow.core.api.kym_external" in text:
-            hits.append(p.name)
-    assert sorted(hits) == ["diameter_kymflow_adapter.py"]
+def test_only_adapter_imports_kym_external() -> None:
+    offenders: list[tuple[str, int, str]] = []
+    for p in ROOT.rglob("*.py"):
+        rel = p.relative_to(ROOT)
+        if p == ALLOWED:
+            continue
+        if any(part in EXCLUDED_DIRS for part in rel.parts):
+            continue
+        source = p.read_text(encoding="utf-8")
+        try:
+            tree = ast.parse(source, filename=str(rel))
+        except SyntaxError as e:
+            raise AssertionError(f"Failed to parse {rel}: {e}") from e
+        for node in ast.walk(tree):
+            if isinstance(node, ast.Import):
+                ... detect alias.name == TARGET_MODULE ...
+            elif isinstance(node, ast.ImportFrom):
+                ... detect node.module == TARGET_MODULE ...
+    if offenders:
+        raise AssertionError("Forbidden kym_external imports found:\n...")
```

## D) Search confirmation
- Searched for `kymflow.core.api.kym_external` in `sandbox/diameter-analysis/gui/*.py` and updated test file.
- Confirmed the only real import statement remains in `gui/diameter_kymflow_adapter.py`.
- Comments/docstrings containing the string do not trigger AST matches (test now inspects import nodes only).

## E) Validation commands run
From `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest -q`
- Result: `45 passed, 1 warning in 1.46s`

## F) Summary of changes
- AST-based boundary test now detects import statements robustly across formatting styles.
- Error output includes violating file path and line number.
- Syntax errors in scanned files now fail with clear parse-location context.

## G) Risks / tradeoffs
- The test excludes `tickets/` and cache/build dirs intentionally; archived ticket snapshots with facade imports are not evaluated.
- AST parsing depends on files being parseable Python; this is now surfaced explicitly as test failure.

## H) Self-critique
- Pros: stronger detection than regex, resilient to multiline and alias imports.
- Cons: still source-scan based (not import graph analysis), but appropriate for boundary enforcement.
- Drift risk: low; allowlist and module target remain explicit constants.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
