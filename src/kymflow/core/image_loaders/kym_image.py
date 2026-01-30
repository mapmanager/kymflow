"""KymImage is a subclass of AcqImage that represents a kymograph image.
"""

from pathlib import Path
from typing import TYPE_CHECKING
import numpy as np
import tifffile

from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.image_loaders.metadata import AcqImgHeader
from kymflow.core.image_loaders.olympus_header.read_olympus_header import _readOlympusHeader  # OlympusHeader

from kymflow.core.utils.logging import get_logger
logger = get_logger(__name__)

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_analysis import KymAnalysis

class KymImage(AcqImage):
    """KymImage is a subclass of AcqImage that represents a kymograph image.

    Rows in np array are time, columns are space.
    """

    def __init__(self, path: str | Path | None = None,
                 img_data: np.ndarray | None = None,
                 channel: int = 1,
                 load_image: bool = False,
                 ):
        
        # Call super().__init__ with load_image=False since KymImage handles its own loading
        # after header discovery (which may discover additional channels)
        super().__init__(path=path, img_data=img_data, channel=channel, load_image=False)

        # Try and load Olympus header from txt file if it exists
        # This discovers additional channels and sets header metadata
        if path is not None:
            path_obj = Path(path)
            _olympusDict = _readOlympusHeader(path_obj)
            if _olympusDict is not None:

                # logger.info('>>> _olympusDict:')
                # from pprint import pprint
                # pprint(_olympusDict)

                numLines = _olympusDict['numLines']
                pixelsPerLine = _olympusDict['pixelsPerLine']
                
                seconds_per_line = _olympusDict['secondsPerLine']
                um_per_pixel = _olympusDict['umPerPixel']
                
                # Create fully-formed header and assign directly
                self._header = AcqImgHeader(
                    shape=(numLines, pixelsPerLine),
                    ndim=2,  # kymographs are always 2D
                    voxels=[seconds_per_line, um_per_pixel],
                    voxels_units=["s", "um"],
                    labels=["Time (s)", "Space (um)"],
                    physical_size=None  # Will be computed
                )
                # Compute physical_size
                self._header.physical_size = self._header.compute_physical_size()
                # Validate consistency
                self._header._validate_consistency()
                
                # Discover and add additional channels from Olympus header
                # _readOlympusHeader returns 'tifChannelPaths' dict mapping channel numbers to paths
                if 'tifChannelPaths' in _olympusDict:
                    tif_channel_paths = _olympusDict['tifChannelPaths']
                    for ch_num, ch_path in tif_channel_paths.items():
                        if ch_path is not None:
                            # Store path in _file_path_dict
                            self._file_path_dict[ch_num] = Path(ch_path)
                            # If this channel already has data, validate shape
                            if self.getChannelData(ch_num) is not None:
                                loaded_shape = self.getChannelData(ch_num).shape
                                if loaded_shape[0] != numLines or loaded_shape[1] != pixelsPerLine:
                                    raise ValueError(f"Image data shape mismatch for channel {ch_num}: {loaded_shape} != {numLines}x{pixelsPerLine}")
                
                # Validate shape if image data is already loaded for the initial channel
                if self.getChannelData(channel) is not None:
                    loaded_shape = self.getChannelData(channel).shape
                    if loaded_shape[0] != numLines or loaded_shape[1] != pixelsPerLine:
                        raise ValueError(f"Image data shape mismatch: {loaded_shape} != {numLines}x{pixelsPerLine}")
            
            # Load image data if requested (only if path was provided and img_data was not)
            if load_image and img_data is None:
                # Load the initial channel if it has a path and no data yet
                initial_channel_path = self.getChannelPath(channel)
                if initial_channel_path is not None and self.getChannelData(channel) is None:
                    self.addColorChannel(channel, None, path=initial_channel_path, load_image=True)
                
                # Load all discovered channels
                for ch_num in self._file_path_dict.keys():
                    if ch_num != channel and self.getChannelData(ch_num) is None:
                        ch_path = self.getChannelPath(ch_num)
                        if ch_path is not None:
                            self.addColorChannel(ch_num, None, path=ch_path, load_image=True)

            # Load metadata (ROIs) if it exists - must happen before analysis loading
            # since analysis reconciles to existing ROIs
            self.load_metadata()
        
        # Always create KymAnalysis (it handles path=None and missing files gracefully)
        from kymflow.core.image_loaders.kym_analysis import KymAnalysis
        self._kym_analysis: "KymAnalysis" = KymAnalysis(self)

    def _load_channel_from_path(self, channel: int, path: Path) -> bool:
        """Load image data from TIFF file path for a specific channel.
        
        Loads a single 2D TIFF file with shape [num_lines, num_pixels].
        Validates that the loaded image is 2D and matches expected shape from header.
        
        Args:
            channel: Channel number (1-based integer key).
            path: File path to load from.
            
        Returns:
            True if loading succeeded, False otherwise.
        """
        try:
            img_array = tifffile.imread(path)
            
            # Validate it's 2D
            if img_array.ndim != 2:
                logger.error(f"KymImage expects 2D images, got {img_array.ndim}D from {path}")
                return False
            
            # Validate shape matches header if header is set
            if self._header.shape is not None:
                expected_shape = self._header.shape
                if img_array.shape != expected_shape:
                    logger.warning(
                        f"Loaded image shape {img_array.shape} doesn't match header shape {expected_shape} "
                        f"for channel {channel} from {path}"
                    )
                    # Still allow it, but log warning
            
            # Add the channel with loaded data
            self._imgData[channel] = img_array
            # logger.info(f"Loaded image data for channel {channel}: {img_array.shape} from {path}")
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to load TIFF from {path} for channel {channel}: {e}")
            return False
    
    def get_kym_analysis(self) -> "KymAnalysis":
        """Get KymAnalysis instance.
        
        Returns:
            KymAnalysis instance for this KymImage.
            
        Raises:
            ValueError: If KymAnalysis was not initialized (should never happen).
        """
        if self._kym_analysis is None:
            raise ValueError("KymAnalysis was not initialized in __init__()")
        return self._kym_analysis
    
    def __str__(self):
        paths_str = ", ".join([f"ch{k}:{v.name}" for k, v in self._file_path_dict.items()])
        return f"KymImage paths=[{paths_str}], shape={self.img_shape}, seconds_per_line={self.seconds_per_line} um_per_pixel={self.um_per_pixel}"

    @property
    def num_lines(self) -> int | None:
        """Number of lines scanned.
        
        Returns None if shape is not available (no header and no loaded data).
        """
        if self.img_shape is None:
            return None
        return self.img_shape[0]
    
    @property
    def pixels_per_line(self) -> int | None:
        """Number of pixels per line.
        
        Returns None if shape is not available (no header and no loaded data).
        """
        if self.img_shape is None:
            return None
        return self.img_shape[1]

    @property
    def seconds_per_line(self) -> float:
        """Temporal resolution in seconds per line scan.
        
        Returns:
            Seconds per line from header.voxels[0], or default 0.001 if not set.
        """
        if self.header.voxels is None or len(self.header.voxels) < 1:
            return 0.001  # Default fallback
        return self.header.voxels[0]

    @property
    def um_per_pixel(self) -> float:
        """Spatial resolution in micrometers per pixel.
        
        Returns:
            Micrometers per pixel from header.voxels[1], or default 1.0 if not set.
        """
        if self.header.voxels is None or len(self.header.voxels) < 2:
            return 1.0  # Default fallback
        return self.header.voxels[1]

    @property
    def image_dur(self) -> float | None:
        """Image duration (s).
        
        Returns None if num_lines is not available.
        """
        if self.num_lines is None:
            return None
        return self.num_lines * self.seconds_per_line
    
    def getRowDict(self) -> dict:
        """Get dictionary with header, file, and analysis information for table/row display.
        
        Overrides base class method to add analysis-specific fields matching summary_row() keys.
        This ensures compatibility with file_table.py which expects these specific keys.
        
        Returns:
            Dictionary containing file info, header fields, and analysis status.
        """
        # Get representative path for folder hierarchy
        representative_path = self._get_representative_path()
        
        # Map to summary_row() keys and add analysis fields
        result = {
            "File Name": representative_path.name if representative_path is not None else None,
            "Analyzed": "✓" if self.get_kym_analysis().has_analysis() else "",
            "Saved": "✓" if not self.get_kym_analysis().is_dirty else "",
            "Num ROIS": self.rois.numRois(),
            "Total Num Velocity Events": self.get_kym_analysis().total_num_velocity_events(),
            "Parent Folder": representative_path.parent.name if representative_path is not None else None,
            "Grandparent Folder": representative_path.parent.parent.name if representative_path is not None and len(representative_path.parent.parts) > 0 else None,
            "pixels": self.pixels_per_line if self.pixels_per_line is not None else "-",
            "lines": self.num_lines if self.num_lines is not None else "-",
            
            # round to 3 decimal
            "duration (s)": round(self.header.physical_size[0], 3) if self.header.physical_size and len(self.header.physical_size) > 0 else "-",

            # round to 1 decimal
            "length (um)": round(self.header.physical_size[1], 1) if self.header.physical_size and len(self.header.physical_size) > 1 else "-",  # abb
            
            "ms/line": round(self.seconds_per_line * 1000, 2) if self.seconds_per_line is not None else "-",
            "um/pixel": self.um_per_pixel if self.um_per_pixel is not None else "-",
            "note": self.experiment_metadata.note or "-",
            "path": str(representative_path) if representative_path is not None else None,  # special case, not in any schema
        }
        
        return result
