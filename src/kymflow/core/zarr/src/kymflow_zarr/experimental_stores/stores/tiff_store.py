# Filename: src/kymflow_zarr/experimental_stores/stores/tiff_store.py
"""TIFF pixel store (eager load; v0.1)."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass
from pathlib import Path
import re
import numpy as np

from .base import ImageInfo


try:
    import tifffile  # type: ignore
except ImportError:  # pragma: no cover
    tifffile = None  # type: ignore


def _require_tifffile() -> None:
    if tifffile is None:  # pragma: no cover
        raise RuntimeError("tifffile required (uv pip install tifffile)")


@dataclass
class TiffPixelStore:
    """PixelStore backed by local TIFF files."""

    def describe(self, key: str) -> ImageInfo:
        _require_tifffile()
        arr = tifffile.imread(str(Path(key)))
        # Axes inference matches kymflow_zarr record defaults for 2D..4D.
        axes = None
        if arr.ndim == 2:
            axes = ("y", "x")
        elif arr.ndim == 3:
            axes = ("z", "y", "x")
        elif arr.ndim == 4:
            axes = ("z", "y", "x", "c")
        return ImageInfo(shape=tuple(arr.shape), ndim=int(arr.ndim), dtype=str(arr.dtype), axes=axes)

    def load_channel(self, key: str, channel: int) -> np.ndarray:
        _require_tifffile()
        if channel != 1:
            # v0.1: multi-file channel support is optional; AcqImageList may group later.
            raise ValueError("TiffPixelStore currently supports channel=1 only")
        return tifffile.imread(str(Path(key)))

    def discover_channel_paths(self, key: str) -> dict[int, str] | None:
        """Best-effort sibling discovery for one-file-per-channel exports.

        Uses the primary key (channel-1 file path) and searches siblings in the same folder
        that share a common stub. This is intentionally conservative; your AcqImageList
        can later manage grouping more robustly.

        Returns:
            Mapping {channel_index: path} if any siblings found; else None.
        """
        p = Path(key)
        folder = p.parent
        # Heuristic: look for 'c1'/'ch1' patterns; replace with c2/c3
        name = p.name
        m = re.search(r"(c|ch)(\d+)", name, flags=re.IGNORECASE)
        if not m:
            return None
        prefix = name[: m.start()]
        suffix = name[m.end() :]
        out = {1: str(p)}
        for ch in range(2, 8):  # small search window
            cand = folder / f"{prefix}{m.group(1)}{ch}{suffix}"
            if cand.exists():
                out[ch] = str(cand)
        return out if len(out) > 1 else None
