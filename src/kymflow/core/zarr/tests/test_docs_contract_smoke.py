"""Smoke checks for zarr docs contract files."""

from __future__ import annotations

from pathlib import Path


DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def test_docs_files_exist() -> None:
    expected = {
        "README.md",
        "api.md",
        "layout.md",
        "workflows.md",
        "incremental.md",
    }
    existing = {p.name for p in DOCS_DIR.glob("*.md")}
    assert expected.issubset(existing)


def test_docs_contract_strings_present() -> None:
    api_text = (DOCS_DIR / "api.md").read_text(encoding="utf-8")
    workflows_text = (DOCS_DIR / "workflows.md").read_text(encoding="utf-8")

    assert "ZarrDataset" in api_text
    assert "ZarrImageRecord" in api_text
    assert "Ingest TIFF" in workflows_text
