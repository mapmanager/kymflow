"""
Repository helpers for discovering and loading kymograph files.

This layer isolates filesystem traversal so GUI/CLI code can rely on a single
API to fetch `KymFile` instances or lightweight metadata dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from kymflow.core.kym_file import KymFile, collect_metadata


@dataclass
class FolderScanResult:
    """Result of scanning a folder for kymograph files.

    Attributes:
        folder: Path to the scanned folder.
        files: List of KymFile instances found in the folder and its subfolders
            (up to the specified depth if recursive scanning was used).
    """

    folder: Path
    files: List[KymFile]


def scan_folder(folder: str | Path, *, load_images: bool = False, depth: int = 1) -> FolderScanResult:
    """Scan a folder for kymograph TIFF files.

    Creates KymFile objects for every .tif file found in the specified folder
    and its subfolders up to the specified depth.

    Args:
        folder: Directory path to scan for TIFF files.
        load_images: If True, TIFF image arrays are loaded immediately.
            If False, images are loaded lazily when accessed. Defaults to False
            for efficient metadata-only workflows.
        depth: Recursive scanning depth. depth=1 includes only base folder
            (code depth 0). depth=2 includes base folder (code depth 0) and
            immediate subfolders (code depth 1). depth=n includes all files from
            code depth 0 up to and including code depth (n-1). Defaults to 1.

    Returns:
        FolderScanResult containing the folder path and list of KymFile
        instances found.
    """
    base = Path(folder).resolve()
    
    # Collect all TIFF files recursively
    all_tif_paths = list(base.glob("**/*.tif"))
    
    # Filter by depth: calculate depth relative to base folder
    # Code depth: base folder = 0, first subfolder = 1, second subfolder = 2, etc.
    # GUI depth N maps to code depths 0 through (N-1)
    #   GUI depth=1 → code depth 0 only (base folder)
    #   GUI depth=2 → code depths 0,1 (base + immediate subfolders)
    #   GUI depth=3 → code depths 0,1,2 (base + subfolders + sub-subfolders)
    filtered_paths = []
    for path in all_tif_paths:
        if not path.is_file():
            continue
        
        # Calculate code depth: number of parent directories between file and base
        # For file at base/sub1/sub2/file.tif with base=base:
        #   relative_path.parts = ['sub1', 'sub2', 'file.tif']
        #   path_depth = len(parts) - 1 = 2 (code depth 2)
        try:
            relative_path = path.relative_to(base)
            # Count the number of parent directories (excluding the file itself)
            # For base/file.tif: parts = ['file.tif'] -> code depth 0
            # For base/sub1/file.tif: parts = ['sub1', 'file.tif'] -> code depth 1
            # For base/sub1/sub2/file.tif: parts = ['sub1', 'sub2', 'file.tif'] -> code depth 2
            path_depth = len(relative_path.parts) - 1
            # Include files where code depth < GUI depth
            if path_depth < depth:
                filtered_paths.append(path)
        except ValueError:
            # Path is not relative to base (shouldn't happen, but handle gracefully)
            continue
    
    tif_paths = sorted(filtered_paths)
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
