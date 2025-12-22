"""General purpose acquired image.
"""

from pathlib import Path
from typing import Tuple
import numpy as np

from kymflow.core.image_loaders.img_acq_header import ImgAcqHeader
from kymflow.core.metadata import ExperimentMetadata
from kymflow.core.utils.logging import get_logger
logger = get_logger(__name__)

class AcqImage:
    """General purpose acquired image.

    If path is specified, allows lazy loading of image data.
    If image is specified, it will be used instead of loading from path.
    """

    def __init__(self, path: str | Path | None,
                 img_data: np.ndarray | None = None,
                 channel: int = 1,
                 ):
        if path is None and img_data is None:
            raise ValueError("Either path or img_data must be provided")
        
        # Initialize header (empty, will be populated during init)
        self._header = ImgAcqHeader()
        
        # Per-channel file paths
        self._file_path_dict: dict[int, Path] = {}
        if path is not None:
            self._file_path_dict[channel] = Path(path)
        
        # Image data dictionary
        self._imgData: dict[int, np.ndarray] = {}
        # dictionary of color channel like {int: np.ndarray}
        
        # Experimental metadata
        self._experiment_metadata = ExperimentMetadata()
        
        if img_data is not None:
            self.addColorChannel(channel, img_data)

        if self._imgData:
            if not self._validate_and_initialize_metadata():
                logger.error("Failed to validate and initialize metadata")
    
    def _get_representative_path(self) -> Path | None:
        """Get a representative path from _file_path_dict.
        
        Returns any channel path since all channels share the same parent folders.
        This method encapsulates the internal representation, making it easy
        to change the data structure in the future.
        
        Returns:
            A Path from any channel, or None if no paths exist.
        """
        if not self._file_path_dict:
            return None
        # Prefer channel 1, otherwise use first available
        if 1 in self._file_path_dict:
            return self._file_path_dict[1]
        return next(iter(self._file_path_dict.values()))
    
    def _compute_parents_from_path(self, path: Path) -> tuple[str | None, str | None, str | None]:
        """Compute parent folder names from a path.
        
        Args:
            path: File path to compute parents from.
            
        Returns:
            Tuple of (parent1, parent2, parent3), where each is a folder name
            or None if that parent doesn't exist. The root '/' is skipped.
        """
        try:
            parts = path.parts
            # For absolute paths like /a/b/c/file.tif:
            # parts = ['/', 'a', 'b', 'c', 'file.tif']
            # parts[-1] is filename, parts[-2] is parent1, etc.
            # For relative paths like a/b/c/file.tif:
            # parts = ['a', 'b', 'c', 'file.tif']
            # parts[-1] is filename, parts[-2] is parent1, etc.
            
            parent1 = None
            parent2 = None
            parent3 = None
            
            # parts[-1] is filename, parts[-2] is parent1, etc.
            # Skip the root '/' if it appears in the parent positions
            if len(parts) >= 2:
                p1 = parts[-2]
                if p1 != '/':  # Skip root
                    parent1 = p1
            if len(parts) >= 3:
                p2 = parts[-3]
                if p2 != '/':  # Skip root
                    parent2 = p2
            if len(parts) >= 4:
                p3 = parts[-4]
                if p3 != '/':  # Skip root
                    parent3 = p3
            
            return (parent1, parent2, parent3)
        except Exception:
            # If path computation fails, return all None
            return (None, None, None)
    
    def _get_representative_channel(self) -> np.ndarray | None:
        """Get a representative channel array from _imgData.
        
        Returns any channel array since all channels share the same shape.
        This method encapsulates the internal representation, making it easy
        to change the data structure in the future.
        
        Returns:
            A numpy array from any channel, or None if no channels exist.
        """
        if not self._imgData:
            return None
        return next(iter(self._imgData.values()))
    
    def _validate_header_field(self, field_name: str, value: list | Tuple, expected_ndim: int | None = None) -> None:
        """Validate that a header field value matches ndim.
        
        Args:
            field_name: Name of the field being validated (for error messages).
            value: The value to validate (list or tuple).
            expected_ndim: Expected ndim value. If None, uses self._header.ndim.
            
        Raises:
            ValueError: If value length doesn't match expected_ndim.
        """
        if expected_ndim is None:
            expected_ndim = self._header.ndim
        
        if expected_ndim is not None and len(value) != expected_ndim:
            raise ValueError(f"{field_name} length {len(value)} doesn't match ndim {expected_ndim}")

    def _validate_and_initialize_metadata(self) -> bool:
        """Validate image dimensions and initialize default metadata.
        
        Returns:
            True if validation and initialization succeeded, False otherwise.
        """
        if not self._imgData:
            return False
        
        # Get shape from any channel (all channels share the same shape)
        representative = self._get_representative_channel()
        if representative is None:
            return False
        ndim = representative.ndim
        if ndim not in (2, 3):
            logger.error(f"Image data must be 2D or 3D, got {ndim}D")
            return False
        
        # Set header fields from loaded data with explicit validation
        shape = representative.shape
        self._header.shape = shape
        self._header.ndim = ndim
        
        # Initialize default metadata with validation
        default_voxels = [1.0] * ndim
        default_units = ["px"] * ndim
        default_labels = [""] * ndim
        
        self._header.voxels = default_voxels
        self._header.voxels_units = default_units
        self._header.labels = default_labels
        self._header.physical_size = self._header.compute_physical_size()
        
        # Validate consistency
        try:
            self._header._validate_consistency()
        except ValueError as e:
            logger.error(f"Header validation failed: {e}")
            return False
        
        return True

    def __str__(self):
        paths_str = ", ".join([f"ch{k}:{v}" for k, v in self._file_path_dict.items()])
        voxels_str = self._header.voxels if self._header.voxels else None
        labels_str = self._header.labels if self._header.labels else None
        return f"paths=[{paths_str}], shape={self.img_shape}, voxels={voxels_str}, labels={labels_str}"

    def addColorChannel(self, color_channel: int, imgData: np.ndarray,
                       path: str | Path | None = None,
                       load_image: bool = False) -> None:
        """Add a new color channel.

        All color channels have the same shape and share:
          voxels, voxels_units, labels, physical_size
        
        Args:
            color_channel: Channel number (1-based integer key).
            imgData: Image array for this channel (can be None if path is provided and load_image=True).
            path: Optional file path for this channel.
            load_image: If True and path is provided, load image from path (must be implemented by derived class).
        
        Raises:
            ValueError: If channel shape doesn't match existing channels or if image dimensions are invalid.
        """
        # Store path if provided
        if path is not None:
            self._file_path_dict[color_channel] = Path(path)
        
        # Load image if requested (derived classes implement _load_channel_from_path)
        if load_image and path is not None:
            if not self._load_channel_from_path(color_channel, Path(path)):
                logger.warning(f"Failed to load image from path for channel {color_channel}")
                return
            # After loading, imgData should be in _imgData, so we can skip the rest
            return
        
        # If imgData is None, we can't proceed
        if imgData is None:
            raise ValueError("Either imgData must be provided, or path with load_image=True")
        
        # Validate image dimensions (must be 2D or 3D)
        if imgData.ndim not in (2, 3):
            raise ValueError(f"Image data must be 2D or 3D, got {imgData.ndim}D")
        
        # Validate shape matches existing channels
        if self._imgData:
            representative = self._get_representative_channel()
            if representative is None:
                return
            existing_shape = representative.shape
            if imgData.shape != existing_shape:
                raise ValueError(
                    f"Channel {color_channel} shape {imgData.shape} doesn't match "
                    f"existing channels {existing_shape}"
                )
        
        self._imgData[color_channel] = imgData
        
        # Set header fields when first channel is added
        if len(self._imgData) == 1:
            # Set shape and ndim directly
            self._header.shape = imgData.shape
            self._header.ndim = imgData.ndim
            # Initialize metadata
            if not self._validate_and_initialize_metadata():
                logger.error(f"Failed to validate and initialize metadata for channel {color_channel}")
    
    def _load_channel_from_path(self, channel: int, path: Path) -> bool:
        """Load image data from path for a specific channel.
        
        This is a stub method that derived classes should override to implement
        file format-specific loading (e.g., TIFF, HDF5, etc.).
        
        Args:
            channel: Channel number (1-based integer key).
            path: File path to load from.
            
        Returns:
            True if loading succeeded, False otherwise.
        """
        logger.warning("_load_channel_from_path() not implemented in base class. Derived classes should override this.")
        return False

    @property
    def header(self) -> ImgAcqHeader:
        """Get the image acquisition header.
        
        Returns:
            ImgAcqHeader instance containing shape, ndim, voxels, labels, etc.
        """
        return self._header
        
    @property
    def img_shape(self) -> Tuple[int, ...] | None:
        """Shape of image data.
        
        Returns shape from header field if set, otherwise from loaded image data.
        """
        # First check header field (available without loading data)
        if self._header.shape is not None:
            return self._header.shape
        
        # Fall back to actual data if available
        representative = self._get_representative_channel()
        if representative is None:
            return None
        # Get shape from any channel (all channels share the same shape)
        return representative.shape

    @property
    def img_ndim(self) -> int | None:
        """Number of dimension in image.
        
        Returns ndim from header field if set, otherwise from loaded image data.
        """
        # First check header field (available without loading data)
        if self._header.ndim is not None:
            return self._header.ndim
        
        # Fall back to actual data if available
        representative = self._get_representative_channel()
        if representative is None:
            return None
        # Get ndim from any channel (all channels share the same shape)
        return representative.ndim

    @property
    def img_num_slices(self) -> int | None:
        if not self._imgData:
            return None
        ndim = self.img_ndim
        if ndim is None:
            return None
        if ndim == 2:
            return 1
        elif ndim == 3:
            return self.img_shape[0] if self.img_shape else None
        else:
            raise ValueError(f"Image data must be 2D or 3D, got {ndim}D")

    @property
    def experiment_metadata(self) -> ExperimentMetadata:
        """Experimental metadata for this image."""
        return self._experiment_metadata
    
    def getChannelPath(self, channel: int) -> Path | None:
        """Get file path for a specific channel.
        
        Args:
            channel: Channel number (1-based integer key).
            
        Returns:
            Path for the specified channel, or None if not set.
        """
        return self._file_path_dict.get(channel)

    def getChannelData(self, channel: int = 1) -> np.ndarray | None:
        """Get the full image data array for a specified channel.
        
        Args:
            channel: Channel number (1-based integer key).
        
        Returns:
            Full numpy array for the specified channel, or None if channel doesn't exist.
        """
        return self._imgData.get(channel)
    
    def getChannelKeys(self) -> list[int]:
        """Get a list of available channel keys.
        
        Returns:
            List of channel keys (integers) that are available in _imgData.
            Returns an empty list if no channels exist.
        """
        return list(self._imgData.keys())
    
    def get_img_slice(self, slice_num: int = 0, channel: int = 1) -> np.ndarray | None:
        """Get image slice from specified channel.

        Args:
            slice_num: Slice number for 3D images (0-based). Ignored for 2D images.
            channel: Channel number (1-based integer key).
        
        Returns:
            Image array slice from the specified channel.
        
        Raises:
            ValueError: If channel doesn't exist or slice number is out of range.
        """
        if channel not in self._imgData:
            raise ValueError(f"Channel {channel} not found. Available channels: {list(self._imgData.keys())}")
        
        channel_data = self._imgData[channel]
        ndim = self.img_ndim
        
        if ndim is None:
            return None
        elif ndim == 2:
            return channel_data
        elif ndim == 3:
            if slice_num < 0 or slice_num >= self.img_num_slices:
                raise ValueError(
                    f"Slice number must be between 0 and {self.img_num_slices-1}, got {slice_num}"
                )
            return channel_data[slice_num, :, :]
        else:
            raise ValueError(f"Image data must be 2D or 3D, got {ndim}D")
    
    def getRowDict(self) -> dict:
        """Get dictionary with header and file information for table/row display.
        
        Returns:
            Dictionary containing file info (path, filename, parent folders) and 
            header fields (ndim, shape, voxels, voxels_units, labels, physical_size).
        """
        # Get representative path (all channels share same parent folders)
        representative_path = self._get_representative_path()
        
        # Compute parent folders on-the-fly
        parent1, parent2, parent3 = self._compute_parents_from_path(representative_path) if representative_path else (None, None, None)
        
        result = {
            'path': str(representative_path) if representative_path is not None else None,
            'filename': representative_path.name if representative_path is not None else None,
            'parent1': parent1,
            'parent2': parent2,
            'parent3': parent3,
            'ndim': self._header.ndim,
            'shape': self._header.shape,
            'voxels': self._header.voxels,
            'voxels_units': self._header.voxels_units,
            'labels': self._header.labels,
            'physical_size': self._header.physical_size,
        }
        return result

