"""Radon velocity analysis report data structure.

This module provides the RadonReport dataclass for representing radon velocity
analysis summary data for a single ROI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RadonReport:
    """Immutable dataclass representing radon velocity analysis summary for a single ROI.
    
    Contains velocity statistics and ROI image statistics from radon-based flow analysis.
    This is an immutable data structure (frozen=True) since it represents completed
    analysis results that should not be modified after creation.
    
    Attributes:
        roi_id: ROI identifier.
        vel_min: Minimum velocity value (mm/s), or None if not available.
        vel_max: Maximum velocity value (mm/s), or None if not available.
        vel_mean: Mean velocity value (mm/s), or None if not available.
        vel_std: Standard deviation of velocity (mm/s), or None if not available.
        vel_se: Standard error of velocity (mm/s), or None if not available.
        vel_cv: Coefficient of variation (std/mean), or None if mean is zero or unavailable.
        img_min: Minimum pixel value in ROI region, or None if not calculated.
        img_max: Maximum pixel value in ROI region, or None if not calculated.
        img_mean: Mean pixel value in ROI region, or None if not calculated.
        img_std: Standard deviation of pixel values in ROI region, or None if not calculated.
        path: Full file path to the kymograph image, or None if not available.
        file_name: File name without extension, or None if not available.
        parent_folder: Parent folder name, or None if not available.
        grandparent_folder: Grandparent folder name, or None if not available.
        rel_path: Path relative to base (folder root or file-list root), for portable CSV.
    """
    
    roi_id: int
    vel_min: Optional[float] = None
    vel_max: Optional[float] = None
    vel_mean: Optional[float] = None
    vel_std: Optional[float] = None
    vel_se: Optional[float] = None
    vel_cv: Optional[float] = None
    img_min: Optional[int] = None
    img_max: Optional[int] = None
    img_mean: Optional[float] = None
    img_std: Optional[float] = None
    path: Optional[str] = None
    file_name: Optional[str] = None
    parent_folder: Optional[str] = None
    grandparent_folder: Optional[str] = None
    rel_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dictionary for JSON/CSV export.
        
        Returns:
            Dictionary with all field values. None values are preserved as None
            (not omitted) to maintain consistent schema.
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RadonReport":
        """Deserialize from a dictionary.
        
        Args:
            data: Dictionary containing RadonReport fields. Unknown keys are ignored.
                Missing keys will use default values (None for optional fields).
        
        Returns:
            RadonReport instance with values from the dictionary.
        """
        # Use dataclass fields to derive field names dynamically
        known_field_names = {f.name for f in fields(cls)}
        
        def _is_none_or_nan(v: Any) -> bool:
            if v is None:
                return True
            if isinstance(v, float) and v != v:  # NaN
                return True
            return False

        # Filter to only known fields and convert types
        filtered_data: Dict[str, Any] = {}
        for key in known_field_names:
            if key in data:
                value = data[key]
                if _is_none_or_nan(value):
                    value = None
                # Type conversions for robustness
                if key == "roi_id":
                    filtered_data[key] = int(value) if value is not None else None
                elif key in ["img_min", "img_max"]:
                    filtered_data[key] = int(value) if value is not None else None
                elif key in ["vel_min", "vel_max", "vel_mean", "vel_std", "vel_se", "vel_cv", "img_mean", "img_std"]:
                    filtered_data[key] = float(value) if value is not None else None
                else:
                    # Strings (path, file_name, parent_folder, grandparent_folder, rel_path)
                    filtered_data[key] = str(value) if value is not None else None
        
        if "roi_id" not in filtered_data:
            raise ValueError("roi_id is required in RadonReport.from_dict()")
        
        return cls(**filtered_data)
