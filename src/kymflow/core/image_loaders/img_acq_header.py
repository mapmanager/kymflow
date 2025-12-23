"""Image acquisition header dataclass.

This module provides ImgAcqHeader, a dataclass for encapsulating header metadata
for acquired images. This includes shape, dimensions, voxel information, and labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


@dataclass
class ImgAcqHeader:
    """Header metadata for acquired images.
    
    Contains all header-related fields that can be set from metadata without
    loading the full image data. This enables lazy loading of image data while
    still providing access to essential metadata.
    
    Attributes:
        shape: Image shape tuple (e.g., (1000, 500) for 2D, (100, 1000, 500) for 3D).
        ndim: Number of dimensions (2 or 3).
        voxels: Physical unit of each voxel (e.g., [0.001, 0.284] for time and space).
        voxels_units: Units for each voxel (e.g., ['s', 'um']).
        labels: Labels for each dimension (e.g., ['time (s)', 'space (um)']).
        physical_size: Physical size along each dimension (shape[i] * voxels[i]).
    """
    
    shape: Tuple[int, ...] | None = None
    ndim: int | None = None
    voxels: list[float] | None = None
    voxels_units: list[str] | None = None
    labels: list[str] | None = None
    physical_size: list[float] | None = None
    
    def __post_init__(self) -> None:
        """Validate consistency after initialization.
        
        Checks that all fields are consistent with ndim if ndim is set.
        This is optional validation - fields can be set incrementally and
        validated explicitly when needed.
        """
        if self.ndim is not None:
            self._validate_consistency()
    
    def _validate_consistency(self) -> None:
        """Validate that all fields are consistent with ndim.
        
        Raises:
            ValueError: If any field length doesn't match ndim.
        """
        if self.ndim is None:
            return
        
        if self.ndim not in (2, 3):
            raise ValueError(f"ndim must be 2 or 3, got {self.ndim}")
        
        # Validate shape
        if self.shape is not None and len(self.shape) != self.ndim:
            raise ValueError(f"shape length {len(self.shape)} doesn't match ndim {self.ndim}")
        
        # Validate voxels
        if self.voxels is not None and len(self.voxels) != self.ndim:
            raise ValueError(f"voxels length {len(self.voxels)} doesn't match ndim {self.ndim}")
        
        # Validate voxels_units
        if self.voxels_units is not None and len(self.voxels_units) != self.ndim:
            raise ValueError(f"voxels_units length {len(self.voxels_units)} doesn't match ndim {self.ndim}")
        
        # Validate labels
        if self.labels is not None and len(self.labels) != self.ndim:
            raise ValueError(f"labels length {len(self.labels)} doesn't match ndim {self.ndim}")
    
    def validate_ndim(self, ndim: int) -> bool:
        """Validate that ndim is consistent with existing header fields.
        
        Args:
            ndim: Number of dimensions to validate.
            
        Returns:
            True if ndim is valid and consistent with existing fields.
        """
        if ndim not in (2, 3):
            return False
        
        # Check consistency with shape
        if self.shape is not None and len(self.shape) != ndim:
            return False
        
        # Check consistency with voxels
        if self.voxels is not None and len(self.voxels) != ndim:
            return False
        
        # Check consistency with voxels_units
        if self.voxels_units is not None and len(self.voxels_units) != ndim:
            return False
        
        # Check consistency with labels
        if self.labels is not None and len(self.labels) != ndim:
            return False
        
        return True
    
    def validate_shape(self, shape: Tuple[int, ...]) -> bool:
        """Validate that shape is consistent with existing header fields.
        
        Args:
            shape: Shape tuple to validate.
            
        Returns:
            True if shape is valid and consistent with existing fields.
        """
        if not shape or len(shape) not in (2, 3):
            return False
        
        ndim = len(shape)
        
        # Check consistency with ndim
        if self.ndim is not None and self.ndim != ndim:
            return False
        
        # Check consistency with voxels
        if self.voxels is not None and len(self.voxels) != ndim:
            return False
        
        # Check consistency with voxels_units
        if self.voxels_units is not None and len(self.voxels_units) != ndim:
            return False
        
        # Check consistency with labels
        if self.labels is not None and len(self.labels) != ndim:
            return False
        
        return True
    
    def compute_physical_size(self) -> list[float] | None:
        """Compute physical size from shape and voxels.
        
        Returns:
            List of physical sizes (shape[i] * voxels[i]) for each dimension,
            or None if shape or voxels are not set.
        """
        if self.shape is None or self.voxels is None:
            return None
        
        if len(self.shape) != len(self.voxels):
            return None
        
        return [s * v for s, v in zip(self.shape, self.voxels)]
    
    # ------------------------------------------------------------------
    # New helper methods for AcqImage
    # ------------------------------------------------------------------
    def set_shape_ndim(self, shape: Tuple[int, ...] | None, ndim: int | None) -> None:
        """Set shape and ndim with consistency validation."""
        if shape is not None:
            self.shape = shape
            if ndim is None:
                ndim = len(shape)
        self.ndim = ndim
        # Validate current state
        self._validate_consistency()

    def init_defaults_from_shape(self) -> None:
        """Initialize default voxels/units/labels based on ndim if not set."""
        if self.ndim is None:
            return
        # Only initialize if currently None
        if self.voxels is None:
            self.voxels = [1.0] * self.ndim
        if self.voxels_units is None:
            self.voxels_units = ["px"] * self.ndim
        if self.labels is None:
            self.labels = [""] * self.ndim
        # Compute physical size
        self.physical_size = self.compute_physical_size()
        # Validate
        self._validate_consistency()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize header to a dictionary for metadata save."""
        return {
            "shape": list(self.shape) if self.shape is not None else None,
            "ndim": self.ndim,
            "voxels": self.voxels,
            "voxels_units": self.voxels_units,
            "labels": self.labels,
            "physical_size": self.physical_size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImgAcqHeader":
        """Deserialize header from a dictionary."""
        header = cls()
        if not data:
            return header
        if "shape" in data:
            header.shape = tuple(data["shape"]) if data["shape"] is not None else None
        if "ndim" in data:
            header.ndim = data["ndim"]
        if "voxels" in data:
            header.voxels = data["voxels"]
        if "voxels_units" in data:
            header.voxels_units = data["voxels_units"]
        if "labels" in data:
            header.labels = data["labels"]
        if "physical_size" in data:
            header.physical_size = data["physical_size"]
        # If physical_size missing but shape+voxels present, compute
        if header.physical_size is None:
            header.physical_size = header.compute_physical_size()
        # Validate consistency
        header._validate_consistency()
        return header

    @classmethod
    def from_data(cls, shape: Tuple[int, ...], ndim: int) -> ImgAcqHeader:
        """Create header from image data shape and ndim.
        
        Initializes default values for voxels, voxels_units, and labels.
        
        Args:
            shape: Image shape tuple.
            ndim: Number of dimensions.
            
        Returns:
            ImgAcqHeader instance with shape and ndim set, and default values
            for other fields.
        """
        header = cls()
        header.shape = shape
        header.ndim = ndim
        header.voxels = [1.0] * ndim
        header.voxels_units = ["px"] * ndim
        header.labels = [""] * ndim
        header.physical_size = header.compute_physical_size()
        return header

