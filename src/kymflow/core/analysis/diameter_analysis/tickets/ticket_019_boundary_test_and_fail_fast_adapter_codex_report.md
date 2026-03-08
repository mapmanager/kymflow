# Ticket 019 Codex Report

Final report path written: `sandbox/diameter-analysis/tickets/ticket_019_boundary_test_and_fail_fast_adapter_codex_report.md`

## Summary of changes
- Updated `list_file_table_kym_images(klist)` in `gui/diameter_kymflow_adapter.py` to fail fast on broken contract.
- Reworked boundary test to detect actual facade import statements (not plain text mentions) across `sandbox/diameter-analysis` recursively.
- Added adapter tests covering fail-fast behavior and normal `.images` contract behavior.

## A) Modified code files
- `sandbox/diameter-analysis/gui/diameter_kymflow_adapter.py`
- `sandbox/diameter-analysis/tests/test_kymflow_boundary.py`
- `sandbox/diameter-analysis/tests/test_kymflow_adapter.py`

## B) Artifacts created
- `sandbox/diameter-analysis/tickets/ticket_019_boundary_test_and_fail_fast_adapter_codex_report.md`

## C) Unified diff (short)

### `sandbox/diameter-analysis/gui/diameter_kymflow_adapter.py`
```diff
@@
 def list_file_table_kym_images(klist: Any) -> list[Any]:
@@
-    try:
-        return list(klist.images)
-    except AttributeError:
-        return list(klist)
+    if not hasattr(klist, "images"):
+        raise TypeError(
+            f"Expected klist with .images (KymImageList contract); got {type(klist)!r}"
+        )
+    return list(klist.images)
```

### `sandbox/diameter-analysis/tests/test_kymflow_boundary.py`
```diff
@@
-from pathlib import Path
+from pathlib import Path
+import re
@@
-GUI_DIR = Path(__file__).resolve().parents[1] / "gui"
+ROOT = Path(__file__).resolve().parents[1]
+ALLOWED = ROOT / "gui" / "diameter_kymflow_adapter.py"
+IMPORT_PATTERNS = [ ... anchored regexes for import statements ... ]
@@
-def test_only_adapter_imports_kym_external() -> None:
-    hits = ... text contains ...
-    assert sorted(hits) == ["diameter_kymflow_adapter.py"]
+def test_only_adapter_imports_kym_external() -> None:
+    offenders = []
+    for p in ROOT.rglob("*.py"):
+        if p == ALLOWED: continue
+        if any(part in {"__pycache__", ".venv", "tickets"} ...): continue
+        if any(pattern.search(text) ...): offenders.append(...)
+    assert offenders == []
```

### `sandbox/diameter-analysis/tests/test_kymflow_adapter.py`
```diff
+def test_list_file_table_kym_images_fails_fast_without_images() -> None:
+    ... pytest.raises(TypeError, match="Expected klist with \\.images") ...
+
+def test_list_file_table_kym_images_uses_images_contract() -> None:
+    ... self.images = [object(), object()] ...
+    assert len(out) == 2
```

## D) Search confirmation
- Search pattern for actual import statements:
  - `^(\s*from\s+kymflow\.core\.api\.kym_external\s+import\s+|\s*import\s+kymflow\.core\.api\.kym_external(\s+as\s+\w+)?\s*$)`
- Result: only `sandbox/diameter-analysis/gui/diameter_kymflow_adapter.py` matched.
- Boundary test uses statement-level regex; comments/docstrings mentioning the module do not trigger failures.

## E) Validation commands run
From `kymflow/sandbox/diameter-analysis/`:

1. `uv run pytest`
- Result: `45 passed, 1 warning`

2. `uv run python run_gui.py`
- Result: app launched successfully (`NiceGUI ready to go on http://127.0.0.1:8000`)
- Process stopped with Ctrl-C (expected for local server run)

## F) Summary of changes
- Adapter now enforces strict `.images` contract for file-table listing.
- Boundary test now checks real import statements recursively.
- Added regression tests for fail-fast adapter contract behavior.

## G) Risks / tradeoffs
- Boundary test excludes `tickets/` to avoid failing on archived snapshot code under ticket artifacts; active code boundary remains enforced.
- If future non-runtime directories are added with example imports, the test may need similar exclusions.

## H) Self-critique
- Pros: minimal, localized changes with strict fail-fast semantics and stronger boundary enforcement.
- Cons: regex-based import detection (instead of AST) could miss unusual multiline/import formatting edge cases.
- Drift risk: low for normal import styles due explicit anchored patterns.

No files outside `kymflow/sandbox/diameter-analysis/` were modified.
