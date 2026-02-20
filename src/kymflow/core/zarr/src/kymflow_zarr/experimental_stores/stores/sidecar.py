# Filename: src/kymflow_zarr/experimental_stores/stores/sidecar.py
"""Sidecar artifact store for TIFF-backed images."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any
from io import BytesIO

import numpy as np


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

    def _array_path(self, key: str, name: str) -> Path:
        p = Path(key)
        return p.with_suffix(f".{name}.npy")

    def save_array_artifact(
        self,
        key: str,
        name: str,
        arr: np.ndarray,
        *,
        axes: list[str] | None = None,
        chunks: tuple[int, ...] | None = None,
    ) -> None:
        p = self._array_path(key, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        buf = BytesIO()
        np.save(buf, arr, allow_pickle=False)
        p.write_bytes(buf.getvalue())

    def load_array_artifact(self, key: str, name: str) -> np.ndarray:
        p = self._array_path(key, name)
        if not p.exists():
            raise FileNotFoundError(f"Missing array artifact: {p}")
        return np.load(BytesIO(p.read_bytes()), allow_pickle=False)

    def list_array_artifacts(self, key: str) -> list[str]:
        p = Path(key)
        prefix = f"{p.stem}."
        out: list[str] = []
        for cand in p.parent.glob(f"{prefix}*.npy"):
            suffix = cand.name[len(prefix):]
            if suffix.endswith(".npy"):
                out.append(suffix[: -len(".npy")])
        return sorted(out)
