# src/kymflow/gui_v2/events_state.py
from __future__ import annotations

from dataclasses import dataclass

from kymflow.core.image_loaders.kym_image import KymImage


@dataclass(frozen=True, slots=True)
class FileListChanged:
    """AppState file list changed (folder scanned/refreshed)."""

    files: list[KymImage]


@dataclass(frozen=True, slots=True)
class SelectedFileChanged:
    """AppState selected file changed."""

    file: KymImage | None
    origin: object | None
