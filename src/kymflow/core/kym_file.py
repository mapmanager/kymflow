"""High-level API for working with kymograph TIFF files.

This module provides the core data structures and functionality for loading,
managing, and analyzing kymograph files. The main entry point is the `KymFile`
class, which encapsulates raw image data, microscope metadata (Olympus txt),
experimental metadata, and analysis products.

The module is designed to support lazy loading - metadata queries do not require
loading full TIFF data, making it efficient for browsing large collections of
files. Analysis algorithms are pluggable through a consistent interface.

Example:
    Basic usage for loading and analyzing a kymograph file:

    ```python
    from kymflow.core.kym_file import KymFile

    kym = KymFile("/path/to/file.tif", load_image=False)
    info = kym.to_metadata_dict()
    image = kym.get_img_channel(channel=1)
    kym.analyze_flow(window_size=16)
    ```
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, Iterator, List, Optional, Tuple

import numpy as np
import tifffile
# import scipy.signal

from kymflow.core.metadata import ExperimentMetadata
from kymflow.core.utils.logging import get_logger
from kymflow.core.image_loaders.kym_image import KymImage

if TYPE_CHECKING:
    from kymflow.core.kym_analysis import KymAnalysis

logger = get_logger(__name__)


class KymFileList:
    """Container for a list of KymFile instances loaded from a folder.
    
    Automatically scans a folder (and optionally subfolders up to a specified depth)
    for TIFF files and creates KymFile instances for each one.
    
    Attributes:
        folder: Path to the scanned folder.
        depth: Recursive scanning depth used. depth=1 includes only base folder
            (code depth 0). depth=2 includes base folder and immediate subfolders
            (code depths 0,1). depth=n includes all files from code depth 0 up to
            and including code depth (n-1).
        load_image: Whether images were loaded immediately or lazily.
        files: List of KymFile instances.
    
    Example:
        ```python
        # Load files from base folder only (depth=1)
        file_list = KymFileList("/path/to/folder", depth=1)
        
        # Access files
        for kym_file in file_list:
            print(kym_file.path)
        ```
    """
    
    def __init__(
        self,
        path: str | Path,
        *,
        depth: int = 1,
        load_image: bool = False,
        glob: str = "*.tif",
        follow_symlinks: bool = False,
    ):
        """Initialize KymFileList and automatically load files.
        
        Args:
            path: Directory path to scan for TIFF files.
            depth: Recursive scanning depth. depth=1 includes only base folder
                (code depth 0). depth=2 includes base folder and immediate subfolders
                (code depths 0,1). depth=n includes all files from code depth 0 up to
                and including code depth (n-1). Defaults to 1.
            load_image: If True, TIFF image arrays are loaded immediately.
                If False, images are loaded lazily when accessed. Defaults to False
                for efficient metadata-only workflows.
            glob: Glob pattern for matching files. Defaults to "*.tif".
            follow_symlinks: If True, follow symbolic links when searching.
                Defaults to False.
        """
        self.folder = Path(path).resolve()
        self.depth = depth
        self.load_image = load_image
        self.files: List[KymFile] = []
        
        # Automatically load files during initialization
        self._load_files(glob=glob, follow_symlinks=follow_symlinks)

    def _load_files(self, glob: str = "*.tif", follow_symlinks: bool = False) -> None:
        """Internal method to scan folder and load KymFile instances.
        
        Uses the same depth-based filtering logic as repository.scan_folder().
        Files that cannot be loaded are silently skipped.
        
        Args:
            glob: Glob pattern for matching files. Defaults to "*.tif".
            follow_symlinks: If True, follow symbolic links when searching.
                Defaults to False.
        """
        if not self.folder.exists() or not self.folder.is_dir():
            logger.warning(f"KymFileList: folder does not exist or is not a directory: {self.folder}")
            return
        
        # Collect all matching files recursively
        if follow_symlinks:
            all_paths = list(self.folder.rglob(glob))
        else:
            all_paths = list(self.folder.glob(f"**/{glob}"))
        
        # Filter by depth: calculate depth relative to base folder
        # Code depth: base folder = 0, first subfolder = 1, second subfolder = 2, etc.
        # GUI depth N maps to code depths 0 through (N-1)
        #   GUI depth=1 → code depth 0 only (base folder)
        #   GUI depth=2 → code depths 0,1 (base + immediate subfolders)
        #   GUI depth=3 → code depths 0,1,2 (base + subfolders + sub-subfolders)
        filtered_paths = []
        for path in all_paths:
            if not path.is_file():
                continue
            
            # Calculate code depth: number of parent directories between file and base
            try:
                relative_path = path.relative_to(self.folder)
                # Count the number of parent directories (excluding the file itself)
                # For base/file.tif: parts = ['file.tif'] -> code depth 0
                # For base/sub1/file.tif: parts = ['sub1', 'file.tif'] -> code depth 1
                # For base/sub1/sub2/file.tif: parts = ['sub1', 'sub2', 'file.tif'] -> code depth 2
                path_depth = len(relative_path.parts) - 1
                # Include files where code depth < GUI depth
                if path_depth < self.depth:
                    filtered_paths.append(path)
            except ValueError:
                # Path is not relative to base (shouldn't happen, but handle gracefully)
                continue
        
        # Sort paths for consistent ordering
        tif_paths = sorted(filtered_paths)
        
        # Create KymFile instances, silently skipping files that can't be loaded
        for tif_path in tif_paths:
            try:
                kym_file = KymFile(tif_path, load_image=self.load_image)
                self.files.append(kym_file)
            except (Exception) as e:
                logger.warning(f"KymFileList: could not load file: {tif_path}")
                logger.warning(f"  -->> e:{e}")
                continue

    def load(self, glob: str = "*.tif", follow_symlinks: bool = False) -> None:
        """Reload files from the folder.
        
        Clears existing files and rescans the folder. Useful for refreshing
        the list after files have been added or removed.
        
        Args:
            glob: Glob pattern for matching files. Defaults to "*.tif".
            follow_symlinks: If True, follow symbolic links when searching.
                Defaults to False.
        """
        self.files.clear()
        self._load_files(glob=glob, follow_symlinks=follow_symlinks)
    
    def reload(self, glob: str = "*.tif", follow_symlinks: bool = False) -> None:
        """Alias for load() method. Reload files from the folder."""
        self.load(glob=glob, follow_symlinks=follow_symlinks)

    def iter_metadata(self, include_analysis: bool = True) -> Iterator[Dict[str, Any]]:
        """Iterate over metadata for all loaded KymFile instances.
        
        Similar to the standalone iter_metadata() function but works on
        already-loaded KymFile instances.
        
        Args:
            include_analysis: If True, include analysis parameters in the
                metadata. Defaults to True.
        
        Yields:
            Dictionary containing metadata for each KymFile, including
            path, filename, Olympus header data, experiment metadata, and
            optionally analysis parameters.
        """
        for kym_file in self.files:
            yield kym_file.to_metadata_dict()

    def collect_metadata(self) -> List[Dict[str, Any]]:
        """Collect metadata for all loaded KymFile instances into a list.
        
        Convenience wrapper around iter_metadata() that collects all results
        into a list. Similar to the standalone collect_metadata() function.
        
        Args:
            include_analysis: If True, include analysis parameters in the
                metadata. Defaults to True.
        
        Returns:
            List of metadata dictionaries, one per loaded KymFile.
        """
        return list(self.iter_metadata())

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, index: int) -> KymFile:
        return self.files[index]

    def __iter__(self) -> Iterator[KymFile]:
        return iter(self.files)

    def __str__(self) -> str:
        return f"KymFileList(folder: {self.folder}, depth: {self.depth}, load_image: {self.load_image}, files: {len(self.files)})"

    def __repr__(self) -> str:
        return self.__str__()

class KymFile:
    """Encapsulates a kymograph TIFF file with metadata and analysis.

    This class provides a unified interface for working with kymograph files,
    including lazy loading of image data, metadata management, and flow analysis.
    The class is designed to support efficient metadata-only workflows where
    full image data is not needed.

    Always use KymFile properties and methods rather than accessing internal
    data structures directly. Key properties include:

    - `duration_seconds`: Total recording duration in seconds
    - `pixels_per_line`: Number of pixels per line (spatial dimension)
    - `num_lines`: Number of lines (time dimension)
    - `acquisition_metadata`: OlympusHeader with metadata (seconds_per_line, um_per_pixel, etc.)
    - `get_img_channel`: Load and return the image array

    Attributes:
        path: Path to the TIFF file.
        experiment_metadata: User-provided experimental metadata.
        acquisition_metadata: Olympus microscope header data.
        kymanalysis: KymAnalysis instance for managing ROIs and analysis.

    Example:
        ```python
        kym = KymFile("file.tif", load_image=False)
        duration = kym.duration_seconds
        pixels = kym.pixels_per_line
        image = kym.get_img_channel(channel=1)
        ```
    """

    def get_img_data(self, channel: int = 1) -> np.ndarray:
        """Get image data.
        
        For Kym, will always be 2d.
        """
        return self.kym_image.get_img_data(channel=channel)

    @property
    def seconds_per_line(self) -> float:
        return self.kym_image.seconds_per_line

    @property
    def um_per_pixel(self) -> float:
        return self.kym_image.um_per_pixel

    @property
    def num_lines(self) -> int:
        return self.kym_image.num_lines

    @property
    def pixels_per_line(self) -> int:
        return self.kym_image.pixels_per_line

    @property
    def image_dur(self) -> float:
        return self.kym_image.image_dur

    def __init__(
        self,
        path: str | Path,
        img_data: np.ndarray | None = None,
        *,
        load_image: bool = False,
    ) -> None:
        """Initialize KymFile instance.

        Loads metadata from the TIFF file and accompanying Olympus header file
        if available. Optionally loads the image data immediately if requested.
        Analysis data is automatically loaded if available.

        Args:
            path: Path to the kymograph TIFF file.
            load_image: If True, load the TIFF image data immediately. If False,
                image will be loaded lazily when needed. Defaults to False for
                efficient metadata-only workflows.
        """
        self.path = Path(path)
        
        self._kym_image: KymImage = KymImage(path, img_data=img_data, load_image=load_image)

        self._experiment_metadata: ExperimentMetadata = ExperimentMetadata()
        # self._header: OlympusHeader = OlympusHeader()  # header is default values

        # # try and load Olympus header from txt file if it exists
        # self._header = OlympusHeader.from_tif(self.path)

        # Initialize KymAnalysis (always present, loads analysis if available)
        from kymflow.core.kym_analysis import KymAnalysis
        self._kym_analysis = KymAnalysis(self, load_analysis=True)

    @property
    def kym_image(self) -> KymImage:
        return self._kym_image

    def __str__(self) -> str:
        return f"KymFile filename:{self.path.name} rois:{self.kymanalysis.num_rois} {self._kym_image}"

    def summary_row(self) -> Dict[str, Any]:
        """Generate tabular summary for file list views.

        Returns a dictionary with key metadata fields formatted for display
        in table views. Includes file name, folder hierarchy, analysis status,
        and key acquisition parameters.

        Returns:
            Dictionary with keys suitable for table display, including file
            name, folder names, analysis status, and metadata values.
        """
        return {
            "File Name": self.path.name,
            "Analyzed": "✓" if self.kymanalysis.has_analysis() else "",
            "Saved": "✓" if not self.kymanalysis._dirty else "",
            "Num ROIS": self.kymanalysis.num_rois,
            "Parent Folder": self.path.parent.name,
            "Grandparent Folder": self.path.parent.parent.name,
            # "Window Points": "-",  # TODO: Get from first analyzed ROI if needed
            "pixels": self.pixels_per_line or "-",
            "lines": self.num_lines or "-",
            "duration (s)": self.duration_seconds or "-",
            "ms/line": round(self.seconds_per_line * 1000, 2),
            "um/pixel": self.um_per_pixel or "-",
            "bits/pixel": self._header.bits_per_pixel or "-",
            "note": self.experiment_metadata.note or "-",
            "path": str(self.path),  # special case, not in any shema
        }

    @classmethod
    def table_column_schema(cls) -> Dict[str, bool]:
        """Return column visibility schema for table display.

        Generates a dictionary mapping column names from summary_row() to
        visibility flags. Reuses existing form schemas where possible to
        avoid duplication of visibility rules.

        Returns:
            Dictionary mapping column names to boolean visibility flags.
            Columns not in the mapping default to visible=True.
        """
        # Mapping from summary_row keys to (dataclass_class, field_name) for schema lookup
        # Keys not in this mapping are derived/computed fields
        schema_field_mapping = {
            "note": (ExperimentMetadata, "note"),
            "um/pixel": (OlympusHeader, "um_per_pixel"),
            # "pixels", "lines", "duration (s)", "ms/line" are derived from OlympusHeader
            # but with different names, so we'd need property mappings - keeping simple for now
        }

        # Override dict for columns not in any schema (derived/computed fields)
        # Defaults to True if not specified
        visibility_overrides = {
            "path": False,  # Always hide - used as row_key only
            # All other columns default to visible=True (don't need to list them)
        }

        result = {}

        # Look up visibility from existing form schemas
        for col_name, (dataclass_cls, field_name) in schema_field_mapping.items():
            form_schema = dataclass_cls.form_schema()
            for field_def in form_schema:
                if field_def["name"] == field_name:
                    result[col_name] = field_def.get("visible", True)
                    break

        # Apply overrides (takes precedence)
        result.update(visibility_overrides)

        return result

    # ------------------------------------------------------------------
    # Metadata exposure
    # ------------------------------------------------------------------
    # abb not used
    def to_metadata_dict(self) -> Dict[str, Any]:
        """Merge all metadata into a single dictionary.

        Combines Olympus header data, experimental metadata, and optionally
        analysis parameters into a unified dictionary structure. This is the
        primary format consumed by GUI tables and CLI scripts.

        Returns:
            Dictionary containing path, filename, and all metadata fields
            from header and experiment metadata.
        """
        header = (
            self.kym_image.header
        )  # header is always loaded in __init__ (can be default)
        merged: Dict[str, Any] = {
            "path": str(self.path),
            "filename": self.path.name,
        }
        merged.update(header.to_dict())
        merged.update(self._experiment_metadata.to_dict())
        # Analysis is now handled by kymanalysis - not included in metadata dict
        # TODO: If needed, can include summary of analyzed ROIs here
        return merged

    @property
    def experiment_metadata(self) -> ExperimentMetadata:
        return self._experiment_metadata

    @property
    def acquisition_metadata(self) -> OlympusHeader:
        return self._header

    @property
    def kymanalysis(self) -> "KymAnalysis":
        """KymAnalysis instance for managing ROIs and flow analysis."""
        return self._kym_analysis

    def update_experiment_metadata(self, **fields: Any) -> None:
        """Update stored experimental metadata fields.

        Updates one or more fields in the experiment metadata. Unknown fields
        are silently ignored. Marks the file as dirty (needs saving).

        Args:
            **fields: Keyword arguments mapping field names to new values.
                Only fields that exist in ExperimentMetadata are updated.
        """
        logger.info(f"fields:{fields}")
        for key, value in fields.items():
            if hasattr(self._experiment_metadata, key):
                setattr(self._experiment_metadata, key, value)
            # Unknown keys are silently ignored (strict schema-only strategy)
        # Note: Experiment metadata changes don't affect analysis dirty state


# ----------------------------------------------------------------------
# Folder level utilities
# ----------------------------------------------------------------------
def iter_metadata(
    root: str | Path,
    *,
    glob: str = "*.tif",
    follow_symlinks: bool = False,
) -> Iterator[Dict[str, Any]]:
    """Iterate over metadata for all TIFF files under a root directory.

    Efficiently scans a directory tree for TIFF files and yields metadata
    dictionaries for each file. Only metadata is loaded - image pixels are
    not read, making this suitable for browsing large collections.

    Args:
        root: Root directory to search, or a single file path.
        glob: Glob pattern for matching files. Defaults to "*.tif".
        follow_symlinks: If True, follow symbolic links when searching.
            Defaults to False.

    Yields:
        Dictionary containing metadata for each TIFF file found, including
        path, filename, Olympus header data, and experiment metadata.
        Files that cannot be loaded are silently skipped.
    """
    base = Path(root)
    paths: Iterable[Path]
    if base.is_dir():
        paths = base.rglob(glob) if follow_symlinks else base.glob(f"**/{glob}")
    else:
        paths = [base]

    for tif_path in paths:
        if not tif_path.is_file():
            continue
        try:
            kym = KymFile(tif_path, load_image=False)
            yield kym.to_metadata_dict()
        except Exception:
            # Metadata collection should be resilient; callers can log errors.
            continue


def collect_metadata(root: str | Path, **kwargs: Any) -> List[Dict[str, Any]]:
    """Collect metadata for all TIFF files under a root directory.

    Convenience wrapper around iter_metadata() that collects all results
    into a list. Useful for GUI applications that need all metadata at once.

    Args:
        root: Root directory to search, or a single file path.
        **kwargs: Additional arguments passed to iter_metadata() (glob,
            follow_symlinks, etc.).

    Returns:
        List of metadata dictionaries, one per TIFF file found.
    """
    return list(iter_metadata(root, **kwargs))
