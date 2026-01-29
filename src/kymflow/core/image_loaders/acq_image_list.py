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
        folder: Path to the scanned folder, or None if uninitialized.
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
        path: str | Path | None,
        *,
        image_cls: Type[T] = AcqImage,
        file_extension: str = ".tif",
        ignore_file_stub: str | None = None,
        depth: int = 1,
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
        """
        # Allow initialization without an initial folder (e.g. GUI startup before a folder
        # is chosen). In that case, keep images empty and skip any scanning.
        if path is None:
            self.folder: Optional[Path] = None
        else:
            self.folder = Path(path).resolve()
        self.depth = depth
        self.file_extension = file_extension
        self.ignore_file_stub = ignore_file_stub
        self.image_cls = image_cls
        self.images: List[T] = []
        
        # Automatically load files during initialization (if we have a folder)
        if self.folder is not None:
            self._load_files()
    
    def _load_files(self) -> None:
        """Internal method to scan folder and create AcqImage instances.
        
        Uses the same depth-based filtering logic as KymFileList._load_files().
        Files that cannot be loaded are silently skipped.
        """
        if self.folder is None:
            logger.debug("AcqImageList._load_files called with folder=None; skipping scan")
            return

        if not self.folder.exists() or not self.folder.is_dir():
            logger.warning(f"AcqImageList: folder does not exist or is not a directory: {self.folder}")
            return
        
        # Build glob pattern from file extension
        # Convert ".tif" to "*.tif"
        if self.file_extension.startswith("."):
            glob_pattern = f"*{self.file_extension}"
        else:
            glob_pattern = f"*.{self.file_extension}"
        
        # abb pyinstaller fail
        # Collect all matching files recursively (glob doesn't follow symlinks by default)
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
            except (ValueError) as e:
                # Path is not relative to base (shouldn't happen, but handle gracefully)
                logger.warning(f"{e}")
                continue
        
        # Sort paths for consistent ordering
        sorted_paths = sorted(filtered_paths)
        
        # Create AcqImage instances, silently skipping files that can't be loaded
        for file_path in sorted_paths:
            try:
                # Create instance WITHOUT loading image data
                # All subclasses now support load_image parameter
                image = self.image_cls(path=file_path, load_image=False)
                self.images.append(image)
            except Exception as e:
                logger.warning(f"AcqImageList: could not load file: {file_path}")
                logger.warning(f"  -->> e:{e}")
                continue
    
    def load(self) -> None:
        """Reload files from the folder.
        
        Clears existing images and rescans the folder. Useful for refreshing
        the list after files have been added or removed.
        """
        self.images.clear()
        if self.folder is None:
            logger.debug("AcqImageList.load called with folder=None; nothing to reload")
            return
        self._load_files()
    
    def reload(self) -> None:
        """Alias for load() method. Reload files from the folder."""
        self.load()
    
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
    
    def load_image_data(self, index: int, channel: int = 1) -> bool:
        """Load image data for a specific image and channel in the list.
        
        Convenience method that calls load_channel() on the image at the specified index.
        Useful for user scripts and tests.
        
        Args:
            index: Index of the image in the list.
            channel: Channel number to load (defaults to 1).
            
        Returns:
            True if loading succeeded, False otherwise.
            
        Raises:
            IndexError: If index is out of range.
        """
        if index < 0 or index >= len(self.images):
            raise IndexError(f"Index {index} out of range for AcqImageList with {len(self.images)} images")
        
        image = self.images[index]
        return image.load_channel(channel)
    
    def load_all_channels(self, index: int) -> dict[int, bool]:
        """Load all available channels for a specific image in the list.
        
        Gets all channel keys from the image's _file_path_dict and loads each one.
        Useful for ensuring all channels are loaded before processing.
        
        Args:
            index: Index of the image in the list.
            
        Returns:
            Dictionary mapping channel numbers to load success status.
            
        Raises:
            IndexError: If index is out of range.
        """
        if index < 0 or index >= len(self.images):
            raise IndexError(f"Index {index} out of range for AcqImageList with {len(self.images)} images")
        
        image = self.images[index]
        result: dict[int, bool] = {}
        
        # Get all channel keys (channels with paths or loaded data)
        channel_keys = image.getChannelKeys()
        
        for channel in channel_keys:
            result[channel] = image.load_channel(channel)
        
        return result
    
    def __len__(self) -> int:
        """Return the number of images in the list."""
        return len(self.images)

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
