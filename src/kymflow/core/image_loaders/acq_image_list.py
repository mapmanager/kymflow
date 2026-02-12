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

import threading
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Generic, Iterator, List, Optional, Type, TypeVar

import pandas as pd

from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.utils.logging import get_logger
from kymflow.core.utils.progress import CancelledError, ProgressCallback, ProgressMessage

logger = get_logger(__name__)

T = TypeVar("T", bound=AcqImage)


class AcqImageList(Generic[T]):
    """Container for a list of AcqImage instances loaded from a folder, a file, or a list of file paths.

    Automatically scans a folder (and optionally subfolders up to a specified depth)
    for files matching a given extension and creates AcqImage instances for each one.
    Files are created WITHOUT loading image data (lazy loading).

    This is a generic class that works with any AcqImage subclass. For KymImage-specific
    functionality (radon analysis, velocity events), use KymImageList instead.

    Modes:
    - Directory scan: `path` is a directory - scans recursively based on `depth`
    - Single file: `path` is a file - loads that one file if it matches filters
    - File list: `file_path_list` is provided - loads specified files (mutually exclusive with `path`)
    - Empty: `path` is None and `file_path_list` is None - creates empty list

    If `path` is a file, and its extension matches `file_extension`, then the resulting
    list contains exactly that one file.

    If `path` is None and `file_path_list` is None, the resulting list is empty (backwards-compat).

    Examples:
        # Generic usage with AcqImage
        image_list = AcqImageList(path="/path/to/folder", image_cls=AcqImage)

        # For KymImage-specific functionality, use KymImageList instead
        from kymflow.core.image_loaders.kym_image_list import KymImageList
        kym_list = KymImageList(path="/path/to/folder")
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
        cancel_event: threading.Event | None = None,
        progress_cb: ProgressCallback | None = None,
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
            self._load_files(
                follow_symlinks=follow_symlinks,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )
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
        self._load_files(
            follow_symlinks=follow_symlinks,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
        )

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

    def _instantiate_image(self, file_path: Path, *, blind_index: int | None = None) -> Optional[T]:
        """Instantiate an image_cls for the file path, without loading image data when possible.
        
        Args:
            file_path: Path to the image file.
            blind_index: Optional index for blinded display (0-based).
        """
        try:
            import inspect

            sig = inspect.signature(self.image_cls.__init__)
            
            # Build kwargs based on signature
            kwargs = {"path": file_path}
            if "load_image" in sig.parameters:
                kwargs["load_image"] = False
            if "_blind_index" in sig.parameters:
                kwargs["_blind_index"] = blind_index
            
            return self.image_cls(**kwargs)
        except Exception as e:
            logger.warning(f"AcqImageList: could not load file: {file_path}")
            logger.warning(f"  -->> e:{e}")
            return None

    def _load_files(
        self,
        *,
        follow_symlinks: bool = False,
        cancel_event: threading.Event | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        """Internal method to load either a single file, scan a folder, or load from file list."""
        images: List[T] = []

        # --- File list mode ---
        if self._file_path_list is not None:
            paths_to_wrap = self._file_path_list
            images = self._wrap_paths(
                paths_to_wrap,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )
            self.images = images
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

            images = self._wrap_paths(
                [self._single_file],
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )
            self.images = images
            return

        # --- Directory-scan mode ---
        if self._folder is None or (not self._folder.exists()) or (not self._folder.is_dir()):
            logger.warning(f"AcqImageList: folder does not exist or is not a directory: {self._folder}")
            return

        # Build glob pattern from file extension
        # Convert ".tif" to "*.tif"
        ext = self._normalized_ext()
        glob_pattern = f"*{ext}" if ext else "*"

        paths_to_wrap = self.collect_paths_from_folder(
            self._folder,
            depth=self.depth,
            file_extension=self.file_extension,
            ignore_file_stub=self.ignore_file_stub,
            follow_symlinks=follow_symlinks,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
        )
        images = self._wrap_paths(
            paths_to_wrap,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
        )
        self.images = images
        return

    def load(
        self,
        follow_symlinks: bool = False,
        *,
        cancel_event: threading.Event | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
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
        self._load_files(
            follow_symlinks=follow_symlinks,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
        )

    def reload(
        self,
        follow_symlinks: bool = False,
        *,
        cancel_event: threading.Event | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        """Alias for load() method.
        
        .. deprecated:: 
            This method is deprecated. Use :meth:`load` instead.
        """
        warnings.warn(
            "reload() is deprecated and will be removed in a future version. Use load() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.load(
            follow_symlinks=follow_symlinks,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
        )

    @classmethod
    def load_from_path(
        cls,
        path: str | Path | None,
        *,
        image_cls: Type[T] = AcqImage,
        file_extension: str = ".tif",
        ignore_file_stub: str | None = None,
        depth: int = 1,
        follow_symlinks: bool = False,
        cancel_event: threading.Event | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> "AcqImageList[T]":
        """Load from a folder, file, or CSV path.

        Args:
            path: Path to a folder, file, CSV, or None.
            image_cls: Class to instantiate for each file. Defaults to AcqImage.
            file_extension: File extension to match (e.g., ".tif").
            ignore_file_stub: Optional filename stub to ignore.
            depth: Folder scan depth (ignored for single files and CSV).
            follow_symlinks: Whether to follow symlinks during folder scan.
            cancel_event: Optional cancellation event.
            progress_cb: Optional progress callback.
        """
        if path is None:
            return cls(
                path=None,
                image_cls=image_cls,
                file_extension=file_extension,
                ignore_file_stub=ignore_file_stub,
                depth=depth,
                follow_symlinks=follow_symlinks,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )

        path_obj = Path(path).expanduser().resolve()

        if path_obj.is_file() and path_obj.suffix.lower() == ".csv":
            file_path_list = cls.collect_paths_from_csv(
                path_obj,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )
            return cls(
                file_path_list=file_path_list,
                image_cls=image_cls,
                file_extension=file_extension,
                ignore_file_stub=ignore_file_stub,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )

        if path_obj.is_file():
            return cls(
                path=path_obj,
                image_cls=image_cls,
                file_extension=file_extension,
                ignore_file_stub=ignore_file_stub,
                depth=0,
                follow_symlinks=follow_symlinks,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )

        return cls(
            path=path_obj,
            image_cls=image_cls,
            file_extension=file_extension,
            ignore_file_stub=ignore_file_stub,
            depth=depth,
            follow_symlinks=follow_symlinks,
            cancel_event=cancel_event,
            progress_cb=progress_cb,
        )

    @staticmethod
    def collect_paths_from_csv(
        csv_path: Path,
        *,
        cancel_event: threading.Event | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> List[Path]:
        """Collect file paths from a CSV with a required 'rel_path' column.
        
        Constructs full paths by combining the CSV file's parent directory with
        each 'rel_path' value from the CSV. Validates that all constructed paths exist.
        
        Args:
            csv_path: Path to CSV file containing 'rel_path' column.
            cancel_event: Optional cancellation event.
            progress_cb: Optional progress callback.
            
        Returns:
            List of validated absolute Path objects.
            
        Raises:
            ValueError: If CSV is invalid, missing 'rel_path' column, or any
                constructed path doesn't exist.
        """
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError("Cancelled before reading CSV.")

        if progress_cb is not None:
            progress_cb(ProgressMessage(phase="read_csv", done=0, total=None, path=csv_path))

        try:
            df = pd.read_csv(csv_path)
        except Exception as exc:
            raise ValueError(f"Failed to read CSV file: {exc}") from exc

        if "rel_path" not in df.columns:
            raise ValueError("CSV must have a 'rel_path' column")

        # Get CSV file's parent directory (base directory for relative paths)
        csv_parent_dir = csv_path.parent.resolve()
        
        # Construct full paths from CSV parent directory + rel_path values
        path_list: List[Path] = []
        invalid_paths: List[str] = []
        
        for idx, rel_path_value in enumerate(df["rel_path"].tolist()):
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError("Cancelled during CSV path construction.")
            
            # Skip None/NaN values
            if pd.isna(rel_path_value) or not rel_path_value:
                continue
            
            # Construct full path: csv_parent_dir / rel_path_value
            full_path = (csv_parent_dir / str(rel_path_value)).resolve()
            
            # Validate path exists
            if not full_path.exists():
                invalid_paths.append(str(rel_path_value))
            else:
                path_list.append(full_path)
        
        # Raise error if any paths don't exist
        if invalid_paths:
            raise ValueError(
                f"CSV contains {len(invalid_paths)} invalid rel_path values that don't exist: "
                f"{', '.join(invalid_paths[:5])}" + ("..." if len(invalid_paths) > 5 else "")
            )
        
        if progress_cb is not None:
            progress_cb(
                ProgressMessage(
                    phase="read_csv",
                    done=len(path_list),
                    total=len(path_list),
                    path=csv_path,
                )
            )

        return path_list

    @staticmethod
    def collect_paths_from_file(
        file_path: Path,
        *,
        file_extension: str,
        ignore_file_stub: str | None,
        cancel_event: threading.Event | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> List[Path]:
        """Validate a single file path and return it if it matches filters."""
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError("Cancelled before file validation.")

        if progress_cb is not None:
            progress_cb(ProgressMessage(phase="scan", done=0, total=None, path=file_path))

        if not file_path.exists() or not file_path.is_file():
            return []

        ext = file_extension.strip()
        if ext and not ext.startswith("."):
            ext = f".{ext}"

        if ext and file_path.suffix.lower() != ext.lower():
            return []

        if ignore_file_stub is not None and ignore_file_stub in file_path.name:
            return []

        temp_list = [file_path]
        if progress_cb is not None:
            progress_cb(ProgressMessage(phase="scan", done=len(temp_list), total=len(temp_list), path=file_path))

        return temp_list

    @staticmethod
    def collect_paths_from_folder(
        folder: Path,
        *,
        depth: int,
        file_extension: str,
        ignore_file_stub: str | None,
        follow_symlinks: bool,
        cancel_event: threading.Event | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> List[Path]:
        """Collect matching file paths from a folder with depth filtering."""
        if progress_cb is not None:
            progress_cb(ProgressMessage(phase="scan", done=0, total=None, path=folder))

        # Build glob pattern from file extension
        ext = file_extension.strip()
        if ext and not ext.startswith("."):
            ext = f".{ext}"
        glob_pattern = f"*{ext}" if ext else "*"

        # Collect all matching files recursively
        if follow_symlinks:
            all_paths = list(folder.rglob(glob_pattern))
        else:
            all_paths = list(folder.glob(f"**/{glob_pattern}"))

        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError("Cancelled during folder scan.")

        # Filter by depth: calculate depth relative to base folder
        # Code depth: base folder = 0, first subfolder = 1, second subfolder = 2, etc.
        # GUI depth N maps to code depths 0 through (N-1)
        filtered_paths: List[Path] = []
        for p in all_paths:
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError("Cancelled during folder scan.")

            if not p.is_file():
                continue

            if ext and p.suffix.lower() != ext.lower():
                continue

            if ignore_file_stub is not None and ignore_file_stub in p.name:
                continue

            try:
                relative_path = p.relative_to(folder)
                path_depth = len(relative_path.parts) - 1
                if path_depth < depth:
                    filtered_paths.append(p)
            except ValueError:
                continue

        filtered_paths = sorted(filtered_paths)

        if progress_cb is not None:
            progress_cb(
                ProgressMessage(
                    phase="scan",
                    done=len(filtered_paths),
                    total=len(filtered_paths),
                    path=folder,
                )
            )

        return filtered_paths

    def _wrap_paths(
        self,
        paths_to_wrap: List[Path],
        *,
        cancel_event: threading.Event | None,
        progress_cb: ProgressCallback | None,
    ) -> List[T]:
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError("Cancelled before wrap.")

        if progress_cb is not None:
            progress_cb(ProgressMessage(phase="wrap", done=0, total=len(paths_to_wrap)))

        wrapped: List[T] = []
        progress_every = 25
        for index, file_path in enumerate(paths_to_wrap):
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError("Cancelled during wrap.")

            if not self._file_matches_filters(file_path):
                logger.warning(
                    "AcqImageList: file does not match filters "
                    f"(extension={self._normalized_ext()}, ignore_file_stub={self.ignore_file_stub}): {file_path}"
                )
                continue

            image = self._instantiate_image(file_path, blind_index=index)
            if image is not None:
                wrapped.append(image)

            if progress_cb is not None and ((index + 1) % progress_every == 0 or (index + 1) == len(paths_to_wrap)):
                progress_cb(
                    ProgressMessage(
                        phase="wrap",
                        done=index + 1,
                        total=len(paths_to_wrap),
                        path=file_path,
                    )
                )

        return wrapped

    def iter_metadata(self, *, blinded: bool = False) -> Iterator[Dict[str, Any]]:
        """Iterate over metadata for all loaded AcqImage instances.
        
        Args:
            blinded: If True, replace file names with "File {index+1}" and grandparent folder with "Blinded".
        """
        for image in self.images:
            yield image.getRowDict(blinded=blinded)

    def collect_metadata(self, *, blinded: bool = False) -> List[Dict[str, Any]]:
        """Collect metadata for all loaded AcqImage instances into a list.
        
        Args:
            blinded: If True, replace file names with "File {index+1}" and grandparent folder with "Blinded".
        """
        return list(self.iter_metadata(blinded=blinded))
    
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
