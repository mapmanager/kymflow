"""General purpose acquired image.
"""

from pathlib import Path
from typing import Tuple, Any
import numpy as np

from kymflow.core.image_loaders.acq_image_header import AcqImgHeader
from kymflow.core.metadata import ExperimentMetadata
from kymflow.core.utils.logging import get_logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kymflow.core.roi import RoiSet

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
        self._header = AcqImgHeader()
        
        # Per-channel file paths
        self._file_path_dict: dict[int, Path] = {}
        if path is not None:
            self._file_path_dict[channel] = Path(path)
        
        # Image data dictionary
        self._imgData: dict[int, np.ndarray] = {}
        # dictionary of color channel like {int: np.ndarray}
        
        # Experimental metadata
        self._experiment_metadata = ExperimentMetadata()
        
        # ROI set (lazy initialization)
        self._roi_set: "RoiSet" | None = None
        
        if img_data is not None:
            self.addColorChannel(channel, img_data)
    
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
    
    @property
    def path(self) -> Path | None:
        """Get representative path (backward compatibility).
        
        Returns:
            Representative path from _file_path_dict, or None if no path available.
        """
        return self._get_representative_path()
    
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
            # After loading, retrieve the data and continue metadata setup
            imgData = self._imgData.get(color_channel)
            if imgData is None:
                logger.warning(f"Image data missing for channel {color_channel} after load")
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
            # Set shape/ndim and initialize defaults via header helpers
            self._header.set_shape_ndim(imgData.shape, imgData.ndim)
            self._header.init_defaults_from_shape()
    
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
    def header(self) -> AcqImgHeader:
        """Get the image acquisition header.
        
        Returns:
            AcqImgHeader instance containing shape, ndim, voxels, labels, etc.
        """
        return self._header
        
    @property
    def img_shape(self) -> Tuple[int, ...] | None:
        """Shape of image data.
        
        Returns shape from header field (no fallback to data).
        """
        return self._header.shape

    @property
    def img_ndim(self) -> int | None:
        """Number of dimension in image.
        
        Returns ndim from header field.
        """
        return self._header.ndim

    @property
    def img_num_slices(self) -> int | None:
        ndim = self.img_ndim
        if ndim is None:
            return None
        if ndim == 2:
            return 1
        if ndim == 3:
            return self.img_shape[0] if self.img_shape else None
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
    
    def update_experiment_metadata(self, **fields: Any) -> None:
        """Update stored experimental metadata fields.
        
        Updates one or more fields in the experiment metadata. Unknown fields
        are silently ignored.
        
        Args:
            **fields: Keyword arguments mapping field names to new values.
                Only fields that exist in ExperimentMetadata are updated.
        """
        for key, value in fields.items():
            if hasattr(self._experiment_metadata, key):
                setattr(self._experiment_metadata, key, value)
    
    @property
    def rois(self) -> "RoiSet":
        """Get RoiSet instance (lazy initialization).
        
        Returns:
            RoiSet instance for managing ROIs associated with this image.
        """
        if self._roi_set is None:
            from kymflow.core.roi import RoiSet
            self._roi_set = RoiSet(self)  # Pass self as acq_image reference
        return self._roi_set
    
    def _get_metadata_path(self) -> Path | None:
        """Get metadata file path from representative image path.
        
        Returns:
            Path to metadata JSON file (same name as image, .json extension),
            or None if no image path is available.
        """
        representative_path = self._get_representative_path()
        if representative_path is None:
            return None
        return representative_path.with_suffix('.json')
    
    def save_metadata(self, path: Path | None = None) -> bool:
        """Save combined metadata to JSON file.
        
        Saves header, experiment_metadata, and ROIs to a JSON file with the
        same name as the image file (different extension).
        
        Args:
            path: Optional path override. If None, uses same name as image file.
            
        Returns:
            True if saved successfully, False if no path available.
        """
        metadata_path = path if path is not None else self._get_metadata_path()
        if metadata_path is None:
            logger.warning("No path available for saving metadata")
            return False
        
        import json
        
        # Prepare header dict
        header_dict = self._header.to_dict()
        
        # Prepare experiment metadata dict
        experiment_dict = self._experiment_metadata.to_dict()
        
        # Prepare ROIs list
        rois_list = self.rois.to_list()
        
        # Combine into metadata structure
        metadata = {
            "version": "1.0",
            "header": header_dict,
            "experiment_metadata": experiment_dict,
            "rois": rois_list,
        }
        
        # Save to JSON file
        try:
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            logger.info(f"Saved metadata to {metadata_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save metadata to {metadata_path}: {e}")
            return False
    
    def load_metadata(self, path: Path | None = None) -> bool:
        """Load combined metadata from JSON file.
        
        Loads header, experiment_metadata, and ROIs from a JSON file. After
        loading ROIs, validates and clamps each ROI to current image bounds
        (ROIs from JSON may be out of bounds).
        
        Args:
            path: Optional path override. If None, uses same name as image file.
            
        Returns:
            True if loaded successfully, False if file doesn't exist.
        """
        metadata_path = path if path is not None else self._get_metadata_path()
        if metadata_path is None:
            logger.warning("No path available for loading metadata")
            return False
        
        if not metadata_path.exists():
            logger.info(f"Metadata file does not exist: {metadata_path}")
            return False
        
        import json
        
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Load header fields
            if "header" in metadata:
                self._header = AcqImgHeader.from_dict(metadata["header"])
            
            # Load experiment metadata
            if "experiment_metadata" in metadata:
                self._experiment_metadata = ExperimentMetadata.from_dict(metadata["experiment_metadata"])
            
            # Load ROIs
            if "rois" in metadata:
                rois_data = metadata["rois"]
                # Use RoiSet.from_list() to create RoiSet with ROIs
                from kymflow.core.roi import RoiSet
                self._roi_set = RoiSet.from_list(rois_data, self)
                
                # Validate and clamp each ROI to current image bounds
                # Store original values before clamping for warning messages
                clamped_count = 0
                for roi in self._roi_set:
                    try:
                        img_w, img_h, num_slices = self._roi_set._get_bounds(roi.channel)
                        
                        # Store original values
                        original_left = roi.left
                        original_top = roi.top
                        original_right = roi.right
                        original_bottom = roi.bottom
                        original_z = roi.z
                        
                        # Validate and clamp z
                        if num_slices == 1:
                            if roi.z != 0:
                                roi.z = 0
                        else:
                            if roi.z < 0:
                                roi.z = 0
                            elif roi.z >= num_slices:
                                roi.z = num_slices - 1
                        
                        # Clamp coordinates
                        from kymflow.core.roi import clamp_coordinates_to_size
                        clamped_left, clamped_top, clamped_right, clamped_bottom = clamp_coordinates_to_size(
                            roi.left, roi.top, roi.right, roi.bottom, img_w, img_h
                        )
                        
                        # Check if anything was clamped
                        was_clamped = (
                            original_left != clamped_left or
                            original_top != clamped_top or
                            original_right != clamped_right or
                            original_bottom != clamped_bottom or
                            original_z != roi.z
                        )
                        
                        if was_clamped:
                            roi.left = clamped_left
                            roi.top = clamped_top
                            roi.right = clamped_right
                            roi.bottom = clamped_bottom
                            clamped_count += 1
                            logger.warning(
                                f"ROI {roi.id} coordinates were clamped on load. "
                                f"Original: left={original_left}, top={original_top}, right={original_right}, bottom={original_bottom}, z={original_z}. "
                                f"Clamped to: left={clamped_left}, top={clamped_top}, right={clamped_right}, bottom={clamped_bottom}, z={roi.z} "
                                f"(image size: {img_w}x{img_h}, num_slices: {num_slices})"
                            )
                    except ValueError as e:
                        logger.warning(f"Could not validate ROI {roi.id} on load: {e}")
                
                if clamped_count > 0:
                    logger.info(f"Clamped {clamped_count} ROI(s) to current image bounds during load")
            
            logger.info(f"Loaded metadata from {metadata_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load metadata from {metadata_path}: {e}")
            return False

