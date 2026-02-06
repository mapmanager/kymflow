"""Container for a list of AcqImage instances loaded from a folder, a single file, or a list of file paths.

AcqImageList automatically scans a folder (and optionally subfolders up to a specified depth)
for files matching a given extension and creates AcqImage instances for each one.

Modes:
- Directory scan: `path` is a directory - scans recursively based on `depth`
- Single file: `path` is a file - loads that one file if it matches filters
- File list: `file_path_list` is provided - loads specified files (mutually exclusive with `path`)
- Empty: `path` is None and `file_path_list` is None - creates empty list

Refactor note:
- The public constructor signature is unchanged in spirit: `path` can now be either a directory or a file.
- NEW: `path` may be None to create an empty list (backwards-compat with your original behavior).
- NEW: `file_path_list` can be provided to load a specific list of files.
- If `path` is a file and it matches `file_extension`, the list will contain exactly that one file.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Generic, Iterator, List, Optional, Type, TypeVar

from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    from kymflow.core.analysis.velocity_events.velocity_events import (
        BaselineDropParams,
        NanGapParams,
        ZeroGapParams,
    )

logger = get_logger(__name__)

T = TypeVar("T", bound=AcqImage)


class AcqImageList(Generic[T]):
    """Container for a list of AcqImage instances loaded from a folder, a file, or a list of file paths.

    Automatically scans a folder (and optionally subfolders up to a specified depth)
    for files matching a given extension and creates AcqImage instances for each one.
    Files are created WITHOUT loading image data (lazy loading).

    Modes:
    - Directory scan: `path` is a directory - scans recursively based on `depth`
    - Single file: `path` is a file - loads that one file if it matches filters
    - File list: `file_path_list` is provided - loads specified files (mutually exclusive with `path`)
    - Empty: `path` is None and `file_path_list` is None - creates empty list

    If `path` is a file, and its extension matches `file_extension`, then the resulting
    list contains exactly that one file.

    If `path` is None and `file_path_list` is None, the resulting list is empty (backwards-compat).
    """

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        file_path_list: list[str] | list[Path] | None = None,
        image_cls: Type[T] = AcqImage,
        file_extension: str = ".tif",
        ignore_file_stub: str | None = None,
        depth: int = 1,
        follow_symlinks: bool = False,
    ):
        """Initialize AcqImageList and automatically load files.

        Args:
            path: Directory path to scan for files, a single file path, or None for empty list.
                Mutually exclusive with `file_path_list`.
            file_path_list: List of file paths to load. Each path should be a full path to a .tif file.
                Mutually exclusive with `path`. If provided, `path` must be None.
            image_cls: Class to instantiate for each file. Defaults to AcqImage.
            file_extension: File extension to match (e.g., ".tif"). Defaults to ".tif".
                Applies to all modes (directory scan, single file, and file_path_list).
            ignore_file_stub: Stub string to ignore in filenames. If a filename contains
                this stub, the file is skipped. Checks filename only, not full path.
                Defaults to None (no filtering).
            depth: Recursive scanning depth. depth=1 includes only base folder
                (code depth 0). depth=2 includes base folder and immediate subfolders
                (code depths 0,1). depth=n includes all files from code depth 0 up to
                and including code depth (n-1). Defaults to 1.
                (Only relevant when `path` is a directory.)
            follow_symlinks: If True, follow symbolic links when searching.
                Defaults to False.
        """
        # Validate mutual exclusivity
        if path is not None and file_path_list is not None:
            raise ValueError("path and file_path_list are mutually exclusive. Provide only one.")

        self.depth = depth
        self.file_extension = file_extension
        self.ignore_file_stub = ignore_file_stub
        self.image_cls = image_cls
        self.images: List[T] = []

        # Internal mode: directory scan vs single-file vs file_list
        self._single_file: Optional[Path] = None
        self._file_path_list: Optional[List[Path]] = None

        # Handle file_path_list mode
        if file_path_list is not None:
            if not file_path_list:
                raise ValueError("file_path_list cannot be empty")
            
            # Normalize and validate paths
            normalized_paths: List[Path] = []
            seen_paths: set[Path] = set()
            
            for file_path in file_path_list:
                resolved_path = Path(file_path).expanduser().resolve()
                
                # Check for duplicates
                if resolved_path in seen_paths:
                    raise ValueError(f"Duplicate file path found: {resolved_path}")
                seen_paths.add(resolved_path)
                
                # Check if file exists
                if not resolved_path.exists():
                    raise ValueError(f"File does not exist: {resolved_path}")
                
                if not resolved_path.is_file():
                    raise ValueError(f"Path is not a file: {resolved_path}")
                
                normalized_paths.append(resolved_path)
            
            self._file_path_list = normalized_paths
            self._path: Optional[Path] = None
            self._folder: Optional[Path] = None
            
            # Automatically load files during initialization
            self._load_files(follow_symlinks=follow_symlinks)
            return

        # Allow initializing an empty list (backwards-compat)
        if path is None:
            self._path: Optional[Path] = None
            self._folder: Optional[Path] = None
            return

        resolved = Path(path).expanduser().resolve()

        # Store the true source path (may be a directory or a file).
        self._path: Optional[Path] = resolved

        # Backwards-compat: `.folder` remains "directory-like".
        # If source is a file, `.folder` is its parent directory.
        self._folder: Optional[Path] = resolved if resolved.is_dir() else resolved.parent

        # Determine single-file mode
        self._single_file = resolved if resolved.is_file() else None

        # Automatically load files during initialization
        self._load_files(follow_symlinks=follow_symlinks)

    @property
    def path(self) -> Optional[Path]:
        """Get the source path.
        
        Returns:
            The source path for directory/file modes, None for empty/file_list modes.
        """
        return self._path

    @property
    def folder(self) -> Optional[Path]:
        """Get the folder path.
        
        Returns:
            The folder path for directory/file modes (parent directory for single files),
            None for empty/file_list modes.
        """
        return self._folder

    def _get_mode(self) -> str:
        """Get the current mode of the AcqImageList.
        
        Returns:
            One of: "empty", "file", "folder", "file_list"
        """
        if self._file_path_list is not None:
            return "file_list"
        if self._path is None:
            return "empty"
        if self._single_file is not None:
            return "file"
        return "folder"

    def _normalized_ext(self) -> str:
        """Return normalized extension with leading dot (e.g. '.tif')."""
        ext = self.file_extension.strip()
        if not ext:
            return ""
        return ext if ext.startswith(".") else f".{ext}"

    def _file_matches_filters(self, file_path: Path) -> bool:
        """Return True if file matches extension and ignore_file_stub rules."""
        if not file_path.is_file():
            return False

        want_ext = self._normalized_ext().lower()
        if want_ext and file_path.suffix.lower() != want_ext:
            return False

        if self.ignore_file_stub is not None and self.ignore_file_stub in file_path.name:
            return False

        return True

    def _instantiate_image(self, file_path: Path) -> Optional[T]:
        """Instantiate an image_cls for the file path, without loading image data when possible."""
        try:
            import inspect

            sig = inspect.signature(self.image_cls.__init__)
            if "load_image" in sig.parameters:
                return self.image_cls(path=file_path, load_image=False)
            return self.image_cls(path=file_path)
        except Exception as e:
            logger.warning(f"AcqImageList: could not load file: {file_path}")
            logger.warning(f"  -->> e:{e}")
            return None

    def _load_files(self, follow_symlinks: bool = False) -> None:
        """Internal method to load either a single file, scan a folder, or load from file list."""

        # --- File list mode ---
        if self._file_path_list is not None:
            for file_path in self._file_path_list:
                if not self._file_matches_filters(file_path):
                    logger.warning(
                        "AcqImageList: file does not match filters "
                        f"(extension={self._normalized_ext()}, ignore_file_stub={self.ignore_file_stub}): {file_path}"
                    )
                    continue
                
                image = self._instantiate_image(file_path)
                if image is not None:
                    self.images.append(image)
            return

        # --- Single-file mode ---
        if self._single_file is not None:
            if not self._single_file.exists():
                logger.warning(f"AcqImageList: file does not exist: {self._single_file}")
                return
            if not self._file_matches_filters(self._single_file):
                # Keep behavior non-throwing; simply create an empty list if it doesn't match.
                logger.warning(
                    "AcqImageList: file does not match filters "
                    f"(extension={self._normalized_ext()}, ignore_file_stub={self.ignore_file_stub}): {self._single_file}"
                )
                return

            image = self._instantiate_image(self._single_file)
            if image is not None:
                self.images.append(image)
            return

        # --- Directory-scan mode ---
        if self._folder is None or (not self._folder.exists()) or (not self._folder.is_dir()):
            logger.warning(f"AcqImageList: folder does not exist or is not a directory: {self._folder}")
            return

        # Build glob pattern from file extension
        # Convert ".tif" to "*.tif"
        ext = self._normalized_ext()
        glob_pattern = f"*{ext}" if ext else "*"

        # Collect all matching files recursively
        if follow_symlinks:
            all_paths = list(self._folder.rglob(glob_pattern))
        else:
            all_paths = list(self._folder.glob(f"**/{glob_pattern}"))

        # Filter by depth: calculate depth relative to base folder
        # Code depth: base folder = 0, first subfolder = 1, second subfolder = 2, etc.
        # GUI depth N maps to code depths 0 through (N-1)
        filtered_paths: List[Path] = []
        for p in all_paths:
            if not self._file_matches_filters(p):
                continue

            # Calculate code depth: number of parent directories between file and base
            try:
                relative_path = p.relative_to(self._folder)
                path_depth = len(relative_path.parts) - 1
                # Include files where code depth < GUI depth
                if path_depth < self.depth:
                    filtered_paths.append(p)
            except ValueError:
                # Path is not relative to base (shouldn't happen, but handle gracefully)
                continue

        # Sort paths for consistent ordering
        for file_path in sorted(filtered_paths):
            image = self._instantiate_image(file_path)
            if image is not None:
                self.images.append(image)

    def load(self, follow_symlinks: bool = False) -> None:
        """Reload files.

        Clears existing images and reloads from the same source:
        - if constructed with a file path: reloads that one file
        - if constructed with a folder path: rescans the folder
        - if constructed with path=None: remains empty
        - if constructed with file_path_list: reloads from the same list

        Args:
            follow_symlinks: If True, follow symbolic links when searching.
                Defaults to False. (Only relevant for directory-scan mode.)
        """
        self.images.clear()
        self._load_files(follow_symlinks=follow_symlinks)

    def reload(self, follow_symlinks: bool = False) -> None:
        """Alias for load() method.
        
        .. deprecated:: 
            This method is deprecated. Use :meth:`load` instead.
        """
        warnings.warn(
            "reload() is deprecated and will be removed in a future version. Use load() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.load(follow_symlinks=follow_symlinks)

    def iter_metadata(self) -> Iterator[Dict[str, Any]]:
        """Iterate over metadata for all loaded AcqImage instances."""
        for image in self.images:
            yield image.getRowDict()

    def collect_metadata(self) -> List[Dict[str, Any]]:
        """Collect metadata for all loaded AcqImage instances into a list."""
        return list(self.iter_metadata())

    def any_dirty_analysis(self) -> bool:
        """Return True if any image has unsaved analysis or metadata."""
        for image in self.images:
            if hasattr(image, "get_kym_analysis"):
                try:
                    if image.get_kym_analysis().is_dirty:
                        return True
                except Exception:
                    continue
        return False

    def total_number_of_event(self) -> int:
        """Return the total number of kym events across all loaded AcqImage instances."""
        total_events = 0
        for image in self.images:
            if hasattr(image, "get_kym_analysis"):
                total_events += image.get_kym_analysis().total_num_velocity_events()
        return total_events

    def detect_all_events(
        self,
        *,
        baseline_drop_params: Optional["BaselineDropParams"] = None,
        nan_gap_params: Optional["NanGapParams"] = None,
        zero_gap_params: Optional["ZeroGapParams"] = None,
    ) -> None:
        """Detect velocity events for all ROIs in all loaded AcqImage instances.
        
        Iterates through all images in the list and for each image that has kym_analysis,
        detects velocity events for all ROIs in that image. Images without kym_analysis
        are silently skipped.
        
        This method does not require image data to be loaded - it works on AcqImage
        instances that have analysis data available.
        
        Args:
            baseline_drop_params: Optional BaselineDropParams instance for baseline-drop detection.
                If None, uses default BaselineDropParams().
            nan_gap_params: Optional NanGapParams instance for NaN-gap detection.
                If None, uses default NanGapParams().
            zero_gap_params: Optional ZeroGapParams instance for zero-gap detection.
                If None, uses default ZeroGapParams().
        """
        for image in self.images:
            if hasattr(image, "get_kym_analysis"):
                for roi_id in image.rois.get_roi_ids():
                    image.get_kym_analysis().run_velocity_event_analysis(
                        roi_id,
                        baseline_drop_params=baseline_drop_params,
                        nan_gap_params=nan_gap_params,
                        zero_gap_params=zero_gap_params,
                    )
    
    def find_by_path(self, path: str | Path) -> Optional[T]:
        """Find an image in the list by its path.
        
        Args:
            path: File path to search for (string or Path). Paths are normalized
                (resolved and expanded) before comparison.
        
        Returns:
            The matching AcqImage instance if found, None otherwise.
        """
        search_path = Path(path).expanduser().resolve()
        
        for image in self.images:
            if image.path is None:
                continue
            # Normalize the image's path for comparison
            image_path = Path(image.path).expanduser().resolve()
            if image_path == search_path:
                return image
        
        return None
    
    def __len__(self) -> int:
        """Return the number of images in the list."""
        return len(self.images)

    def __getitem__(self, index: int) -> T:
        """Get image by index."""
        return self.images[index]

    def __iter__(self) -> Iterator[T]:
        """Make AcqImageList iterable over its images."""
        return iter(self.images)

    def __str__(self) -> str:
        mode = self._get_mode()
        if mode == "file_list":
            src = f"{len(self._file_path_list)} files" if self._file_path_list else "0 files"
        elif mode == "file":
            src = self._single_file
        elif mode == "folder":
            src = self._folder or self._path
        else:  # empty
            src = None
        return (
            f"AcqImageList(mode: {mode}, source: {src}, depth: {self.depth}, "
            f"file_extension: {self.file_extension}, ignore_file_stub: {self.ignore_file_stub}, "
            f"images: {len(self.images)})"
        )

    def __repr__(self) -> str:
        return self.__str__()