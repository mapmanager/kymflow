# Filename: src/kymflow_zarr/experimental_stores/stores/base.py
"""Protocols for pixel and artifact backends."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

from dataclasses import dataclass
from typing import Any, Protocol, Sequence, runtime_checkable

import numpy as np

ImageKey = str


@dataclass(frozen=True)
class ImageInfo:
    """Minimal image description."""

    shape: tuple[int, ...]
    ndim: int
    dtype: str
    axes: Sequence[str] | None = None


@runtime_checkable
class PixelStore(Protocol):
    """Load pixels for a logical image key."""

    def describe(self, key: ImageKey) -> ImageInfo:
        raise NotImplementedError

    def load_channel(self, key: ImageKey, channel: int) -> np.ndarray:
        raise NotImplementedError

    def discover_channel_paths(self, key: ImageKey) -> dict[int, str] | None:
        """Optional: return mapping of channel->path for multi-file channel exports."""
        return None


@runtime_checkable
class ArtifactStore(Protocol):
    """Load/save per-image artifacts (dicts + tables)."""

    def load_dict(self, key: ImageKey, name: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def save_dict(self, key: ImageKey, name: str, dct: dict[str, Any]) -> None:
        raise NotImplementedError
