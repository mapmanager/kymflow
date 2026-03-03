from __future__ import annotations

from pathlib import Path


GUI_DIR = Path(__file__).resolve().parents[1] / "gui"


def test_only_adapter_imports_kym_external() -> None:
    hits: list[str] = []
    for p in GUI_DIR.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        if "kymflow.core.api.kym_external" in text:
            hits.append(p.name)
    assert sorted(hits) == ["diameter_kymflow_adapter.py"]
