"""
Repository helpers for discovering and loading kymograph files.

This layer isolates filesystem traversal so GUI/CLI code can rely on a single
API to fetch `KymFile` instances or lightweight metadata dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from .kym_file import KymFile, collect_metadata


@dataclass
class FolderScanResult:
    """Convenience bundle for folder level information."""

    folder: Path
    files: List[KymFile]


def scan_folder(folder: str | Path, *, load_images: bool = False) -> FolderScanResult:
    """
    Create `KymFile` objects for every `.tif` in `folder`.

    Parameters
    ----------
    folder:
        Directory to inspect (non-recursive).
    load_images:
        If True, TIFF arrays are loaded immediately; otherwise, they are loaded
        lazily when accessed.
    """
    base = Path(folder)
    tif_paths = sorted(
        path for path in base.glob("*.tif") if path.is_file()
    )
    files = [KymFile(path, load_image=load_images) for path in tif_paths]
    return FolderScanResult(folder=base, files=files)


def metadata_table(folder: str | Path) -> Sequence[dict]:
    """
    Return metadata dictionaries for each TIFF under `folder`.

    Uses the lighter-weight `collect_metadata` helper so callers can quickly
    populate tables without instantiating `KymFile` objects.
    """
    return collect_metadata(folder)
