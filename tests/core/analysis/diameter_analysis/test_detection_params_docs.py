from __future__ import annotations

from dataclasses import fields
from importlib import import_module
from pathlib import Path

from kymflow.core.analysis.diameter_analysis import DiameterDetectionParams


def test_detection_params_doc_covers_all_fields() -> None:
    module = import_module(DiameterDetectionParams.__module__)
    doc_path = Path(module.__file__).resolve().parent / "docs" / "detection_params.md"
    text = doc_path.read_text(encoding="utf-8")
    for f in fields(DiameterDetectionParams):
        assert f"`{f.name}`" in text
