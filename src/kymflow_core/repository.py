"""
Repository helpers for discovering and loading kymograph files.

This layer isolates filesystem traversal so GUI/CLI code can rely on a single
API to fetch `KymFile` instances or lightweight metadata dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from .kym_file import KymFile, collect_metadata


@dataclass
class FolderScanResult:
    """Result of scanning a folder for kymograph files.

    Attributes:
        folder: Path to the scanned folder.
        files: List of KymFile instances found in the folder.
    """

    folder: Path
    files: List[KymFile]


def scan_folder(folder: str | Path, *, load_images: bool = False) -> FolderScanResult:
    """Scan a folder for kymograph TIFF files.

    Creates KymFile objects for every .tif file found in the specified folder.
    The scan is non-recursive (only direct children of the folder are checked).

    Args:
        folder: Directory path to scan for TIFF files.
        load_images: If True, TIFF image arrays are loaded immediately.
            If False, images are loaded lazily when accessed. Defaults to False
            for efficient metadata-only workflows.

    Returns:
        FolderScanResult containing the folder path and list of KymFile
        instances found.
    """
    base = Path(folder)
    tif_paths = sorted(path for path in base.glob("*.tif") if path.is_file())
    files = [KymFile(path, load_image=load_images) for path in tif_paths]
    return FolderScanResult(folder=base, files=files)


def metadata_table(folder: str | Path) -> Sequence[dict]:
    """Get metadata dictionaries for all TIFF files in a folder.

    Lightweight alternative to scan_folder() that returns metadata dictionaries
    instead of KymFile objects. Useful for quickly populating tables without
    the overhead of instantiating full KymFile objects.

    Args:
        folder: Directory path to scan for TIFF files.

    Returns:
        Sequence of metadata dictionaries, one per TIFF file found.
    """
    return collect_metadata(folder)
