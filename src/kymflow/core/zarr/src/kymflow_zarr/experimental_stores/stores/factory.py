# Filename: src/kymflow_zarr/experimental_stores/stores/factory.py
"""Store selection helpers."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from pathlib import Path

from .sidecar import SidecarArtifactStore
from .tiff_store import TiffPixelStore
from .zarr_store import ZarrStore


def stores_for_path(path: str | Path):
    p = Path(path)
    if p.suffix.lower() == ".zarr":
        z = ZarrStore(str(p))
        return z, z
    return TiffPixelStore(), SidecarArtifactStore()
