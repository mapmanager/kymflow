from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ROOT / "gui" / "diameter_kymflow_adapter.py"
EXCLUDED_DIRS = {
    "__pycache__",
    ".venv",
    ".pytest_cache",
    "dist",
    "build",
    "tickets",
}
TARGET_MODULE = "kymflow.core.api.kym_external"


def test_only_adapter_imports_kym_external() -> None:
    offenders: list[tuple[str, int, str]] = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT)
        if p == ALLOWED:
            continue
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue

        source = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(rel))
        except SyntaxError as e:
            raise AssertionError(f"Failed to parse {rel}: {e}") from e

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == TARGET_MODULE:
                        offenders.append((str(rel), int(node.lineno), f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom):
                if node.module == TARGET_MODULE:
                    offenders.append((str(rel), int(node.lineno), f"from {node.module} import ..."))

    if offenders:
        details = "\n".join(f"- {path}:{line}: {stmt}" for path, line, stmt in offenders)
        raise AssertionError(f"Forbidden kym_external imports found:\n{details}")
