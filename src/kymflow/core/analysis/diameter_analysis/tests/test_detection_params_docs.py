from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from kymflow.core.analysis.diameter_analysis import DiameterDetectionParams


def test_detection_params_doc_covers_all_fields() -> None:
    doc_path = Path(__file__).resolve().parents[1] / "docs" / "detection_params.md"
    text = doc_path.read_text(encoding="utf-8")
    for f in fields(DiameterDetectionParams):
        assert f"`{f.name}`" in text
