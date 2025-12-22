"""Container for a list of AcqImage instances loaded from a folder.

AcqImageList automatically scans a folder (and optionally subfolders up to a specified depth)
for files matching a given extension and creates AcqImage instances for each one.
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
    """Container for a list of AcqImage instances loaded from a folder.
    
    Automatically scans a folder (and optionally subfolders up to a specified depth)
    for files matching a given extension and creates AcqImage instances for each one.
    Files are created WITHOUT loading image data (lazy loading).
    
    Attributes:
        folder: Path to the scanned folder.
        depth: Recursive scanning depth used. depth=1 includes only base folder
            (code depth 0). depth=2 includes base folder and immediate subfolders
            (code depths 0,1). depth=n includes all files from code depth 0 up to
            and including code depth (n-1).
        file_extension: File extension used for matching (e.g., ".tif").
        ignore_file_stub: Stub string to ignore in filenames (e.g., "C002").
        image_cls: Class used to instantiate images.
        images: List of AcqImage instances.
    
    Example:
        ```python
        # Load KymImage files from base folder only (depth=1)
        image_list = AcqImageList(
            path="/path/to/folder",
            image_cls=KymImage,
            file_extension=".tif",
            ignore_file_stub="C002",
            depth=1
        )
        
        # Access images
        for image in image_list:
            print(image.getRowDict())
        ```
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
            path: Directory path to scan for files.
            image_cls: Class to instantiate for each file. Defaults to AcqImage.
            file_extension: File extension to match (e.g., ".tif"). Defaults to ".tif".
            ignore_file_stub: Stub string to ignore in filenames. If a filename contains
                this stub, the file is skipped. Checks filename only, not full path.
                Defaults to None (no filtering).
            depth: Recursive scanning depth. depth=1 includes only base folder
                (code depth 0). depth=2 includes base folder and immediate subfolders
                (code depths 0,1). depth=n includes all files from code depth 0 up to
                and including code depth (n-1). Defaults to 1.
            follow_symlinks: If True, follow symbolic links when searching.
                Defaults to False.
        """
        self.folder = Path(path).resolve()
        self.depth = depth
        self.file_extension = file_extension
        self.ignore_file_stub = ignore_file_stub
        self.image_cls = image_cls
        self.images: List[T] = []
        
        # Automatically load files during initialization
        self._load_files(follow_symlinks=follow_symlinks)
    
    def _load_files(self, follow_symlinks: bool = False) -> None:
        """Internal method to scan folder and create AcqImage instances.
        
        Uses the same depth-based filtering logic as KymFileList._load_files().
        Files that cannot be loaded are silently skipped.
        
        Args:
            follow_symlinks: If True, follow symbolic links when searching.
                Defaults to False.
        """
        if not self.folder.exists() or not self.folder.is_dir():
            logger.warning(f"AcqImageList: folder does not exist or is not a directory: {self.folder}")
            return
        
        # Build glob pattern from file extension
        # Convert ".tif" to "*.tif"
        if self.file_extension.startswith("."):
            glob_pattern = f"*{self.file_extension}"
        else:
            glob_pattern = f"*.{self.file_extension}"
        
        # Collect all matching files recursively
        if follow_symlinks:
            all_paths = list(self.folder.rglob(glob_pattern))
        else:
            all_paths = list(self.folder.glob(f"**/{glob_pattern}"))
        
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
            
            # Filter by ignore_file_stub (filename only)
            if self.ignore_file_stub is not None:
                if self.ignore_file_stub in path.name:
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
        sorted_paths = sorted(filtered_paths)
        
        # Create AcqImage instances, silently skipping files that can't be loaded
        for file_path in sorted_paths:
            try:
                # Create instance WITHOUT loading image data
                # Check if the class accepts load_image parameter
                import inspect
                sig = inspect.signature(self.image_cls.__init__)
                if 'load_image' in sig.parameters:
                    image = self.image_cls(path=file_path, load_image=False)
                else:
                    # Base AcqImage doesn't have load_image parameter
                    image = self.image_cls(path=file_path)
                self.images.append(image)
            except Exception as e:
                logger.warning(f"AcqImageList: could not load file: {file_path}")
                logger.warning(f"  -->> e:{e}")
                continue
    
    def load(self, follow_symlinks: bool = False) -> None:
        """Reload files from the folder.
        
        Clears existing images and rescans the folder. Useful for refreshing
        the list after files have been added or removed.
        
        Args:
            follow_symlinks: If True, follow symbolic links when searching.
                Defaults to False.
        """
        self.images.clear()
        self._load_files(follow_symlinks=follow_symlinks)
    
    def reload(self, follow_symlinks: bool = False) -> None:
        """Alias for load() method. Reload files from the folder."""
        self.load(follow_symlinks=follow_symlinks)
    
    def iter_metadata(self) -> Iterator[Dict[str, Any]]:
        """Iterate over metadata for all loaded AcqImage instances.
        
        Yields:
            Dictionary containing metadata for each AcqImage via getRowDict().
        """
        for image in self.images:
            yield image.getRowDict()
    
    def collect_metadata(self) -> List[Dict[str, Any]]:
        """Collect metadata for all loaded AcqImage instances into a list.
        
        Convenience wrapper around iter_metadata() that collects all results
        into a list.
        
        Returns:
            List of metadata dictionaries, one per loaded AcqImage.
        """
        return list(self.iter_metadata())
    
    def __len__(self) -> int:
        """Return the number of images in the list."""
        return len(self.images)
    
    def __getitem__(self, index: int) -> T:
        """Get image by index.
        
        Args:
            index: Index of the image to retrieve.
            
        Returns:
            AcqImage instance at the specified index.
        """
        return self.images[index]
    
    def __iter__(self) -> Iterator[T]:
        """Make AcqImageList iterable over its images.
        
        Yields:
            AcqImage instances.
        """
        return iter(self.images)
    
    def __str__(self) -> str:
        """String representation."""
        return (
            f"AcqImageList(folder: {self.folder}, depth: {self.depth}, "
            f"file_extension: {self.file_extension}, ignore_file_stub: {self.ignore_file_stub}, "
            f"images: {len(self.images)})"
        )
    
    def __repr__(self) -> str:
        """String representation."""
        return self.__str__()
