"""Container for a list of AcqImage instances loaded from a folder *or* a single file.

AcqImageList automatically scans a folder (and optionally subfolders up to a specified depth)
for files matching a given extension and creates AcqImage instances for each one.

Refactor note:
- The public constructor signature is unchanged: `path` can now be either a directory *or* a file.
- If `path` is a file and it matches `file_extension`, the list will contain exactly that one file.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Generic, Iterator, List, Optional, Type, TypeVar

from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

T = TypeVar("T", bound=AcqImage)


class AcqImageList(Generic[T]):
    """Container for a list of AcqImage instances loaded from a folder or a file.

    Automatically scans a folder (and optionally subfolders up to a specified depth)
    for files matching a given extension and creates AcqImage instances for each one.
    Files are created WITHOUT loading image data (lazy loading).

    If `path` is a file, and its extension matches `file_extension`, then the resulting
    list contains exactly that one file.

    Attributes:
        path: The resolved input path (directory or file).
        folder: The scanned folder when `path` is a directory; for file-input, this is
            the parent directory of the file (kept for backwards-compat).
        depth: Recursive scanning depth used (only relevant for directory mode).
        file_extension: File extension used for matching (e.g., ".tif").
        ignore_file_stub: Stub string to ignore in filenames (e.g., "C002").
        image_cls: Class used to instantiate images.
        images: List of AcqImage instances.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        image_cls: Type[T] = AcqImage,
        file_extension: str = ".tif",
        ignore_file_stub: str | None = None,
        depth: int = 1,
        follow_symlinks: bool = False,
    ):
        """Initialize AcqImageList and automatically load files.

        Args:
            path: Directory path to scan for files, or a single file path.
            image_cls: Class to instantiate for each file. Defaults to AcqImage.
            file_extension: File extension to match (e.g., ".tif"). Defaults to ".tif".
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
        resolved = Path(path).expanduser().resolve()

        # Keep the original "folder-based" public surface, but also store the
        # true source path (which may be a file).
        self.path: Path = resolved

        # Backwards-compat:
        # Historically `folder` was always the resolved directory passed in.
        # For file-input, callers sometimes still expect `.folder` to be a directory-like
        # thing (e.g. used for display). We set it to the file's parent in that case.
        self.folder: Path = resolved if resolved.is_dir() else resolved.parent

        self.depth = depth
        self.file_extension = file_extension
        self.ignore_file_stub = ignore_file_stub
        self.image_cls = image_cls
        self.images: List[T] = []

        # Internal mode: directory scan vs single-file
        self._single_file: Optional[Path] = resolved if resolved.is_file() else None

        # Automatically load files during initialization
        self._load_files(follow_symlinks=follow_symlinks)

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
        """Internal method to load either a single file or scan a folder."""

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
        if not self.folder.exists() or not self.folder.is_dir():
            logger.warning(f"AcqImageList: folder does not exist or is not a directory: {self.folder}")
            return

        # Build glob pattern from file extension
        # Convert ".tif" to "*.tif"
        ext = self._normalized_ext()
        glob_pattern = f"*{ext}" if ext else "*"

        # Collect all matching files recursively
        if follow_symlinks:
            all_paths = list(self.folder.rglob(glob_pattern))
        else:
            all_paths = list(self.folder.glob(f"**/{glob_pattern}"))

        # Filter by depth: calculate depth relative to base folder
        # Code depth: base folder = 0, first subfolder = 1, second subfolder = 2, etc.
        # GUI depth N maps to code depths 0 through (N-1)
        filtered_paths: List[Path] = []
        for p in all_paths:
            if not self._file_matches_filters(p):
                continue

            # Calculate code depth: number of parent directories between file and base
            try:
                relative_path = p.relative_to(self.folder)
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

        Args:
            follow_symlinks: If True, follow symbolic links when searching.
                Defaults to False.
        """
        self.images.clear()
        self._load_files(follow_symlinks=follow_symlinks)

    def reload(self, follow_symlinks: bool = False) -> None:
        """Alias for load() method."""
        self.load(follow_symlinks=follow_symlinks)

    def iter_metadata(self) -> Iterator[Dict[str, Any]]:
        """Iterate over metadata for all loaded AcqImage instances."""
        for image in self.images:
            yield image.getRowDict()

    def collect_metadata(self) -> List[Dict[str, Any]]:
        """Collect metadata for all loaded AcqImage instances into a list."""
        return list(self.iter_metadata())

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
        mode = "file" if self._single_file is not None else "folder"
        src = self._single_file if self._single_file is not None else self.folder
        return (
            f"AcqImageList(mode: {mode}, source: {src}, depth: {self.depth}, "
            f"file_extension: {self.file_extension}, ignore_file_stub: {self.ignore_file_stub}, "
            f"images: {len(self.images)})"
        )

    def __repr__(self) -> str:
        return self.__str__()