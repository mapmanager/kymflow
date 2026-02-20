# Filename: src/kymflow_zarr/experimental_stores/stores/sidecar.py
"""Sidecar artifact store for TIFF-backed images."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any


@dataclass
class SidecarArtifactStore:
    """Artifacts stored adjacent to a primary image file."""

    suffix: str = ".metadata.json"

    def _path(self, key: str, name: str) -> Path:
        # Store as: <file>.<name>.json
        p = Path(key)
        return p.with_suffix(f".{name}.json")

    def load_dict(self, key: str, name: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        p = self._path(key, name)
        if not p.exists():
            return {} if default is None else default
        return json.loads(p.read_text(encoding="utf-8"))

    def save_dict(self, key: str, name: str, dct: dict[str, Any]) -> None:
        p = self._path(key, name)
        p.write_text(json.dumps(dct, indent=2, default=str), encoding="utf-8")
