"""Radon velocity analysis report data structure.

This module provides the RadonReport dataclass for representing radon velocity
analysis summary data for a single ROI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, Optional, get_origin, get_args


@dataclass(frozen=True)
class RadonReport:
    """Immutable dataclass representing radon velocity analysis summary for a single ROI.
    
    Contains velocity statistics and ROI image statistics from radon-based flow analysis.
    This is an immutable data structure (frozen=True) since it represents completed
    analysis results that should not be modified after creation.
    
    Attributes:
        roi_id: ROI identifier.
        channel: Channel index from radon metadata, or None if not available.
        vel_min: Minimum velocity value (mm/s), or None if not available.
        vel_max: Maximum velocity value (mm/s), or None if not available.
        vel_mean: Mean velocity value (mm/s), or None if not available.
        vel_std: Standard deviation of velocity (mm/s), or None if not available.
        vel_se: Standard error of velocity (mm/s), or None if not available.
        vel_cv: Coefficient of variation (std/mean), or None if mean is zero or unavailable.
        vel_n_nan: Number of NaN values in velocity array, or None if not available.
        vel_n_zero: Number of zero values in velocity array, or None if not available.
        vel_n_big: Number of "big" velocity values (> mean + 2*std), or None if not available.
        img_min: Minimum pixel value in ROI region, or None if not calculated.
        img_max: Maximum pixel value in ROI region, or None if not calculated.
        img_mean: Mean pixel value in ROI region, or None if not calculated.
        img_std: Standard deviation of pixel values in ROI region, or None if not calculated.
        path: Full file path to the kymograph image, or None if not available.
        file_name: File name without extension, or None if not available.
        parent_folder: Parent folder name, or None if not available.
        grandparent_folder: Grandparent folder name, or None if not available.
        rel_path: Path relative to base (folder root or file-list root), for portable CSV.
        accepted: KymAnalysis-level boolean indicating whether this analysis has been accepted
            by the user (True/False), or None if not available. This is set at the image level
            and applies to all ROIs in the image.
        treatment: From AcqImage experimental metadata (e.g. grandparent_folder concept).
        condition: From AcqImage experimental metadata (e.g. Control, AngII).
        date: From AcqImage experimental metadata (e.g. parent_folder concept).
    """
    
    roi_id: int
    channel: Optional[int] = None
    vel_min: Optional[float] = None
    vel_max: Optional[float] = None
    vel_mean: Optional[float] = None
    vel_std: Optional[float] = None
    vel_se: Optional[float] = None
    vel_cv: Optional[float] = None
    vel_n_nan: Optional[int] = None
    vel_n_zero: Optional[int] = None
    vel_n_big: Optional[int] = None

    users_added_count: Optional[int] = None
    users_added_dur_sum: Optional[float] = None
    users_added_dur_mean: Optional[float] = None

    img_min: Optional[int] = None
    img_max: Optional[int] = None
    img_mean: Optional[float] = None
    img_std: Optional[float] = None
    path: Optional[str] = None
    file_name: Optional[str] = None
    parent_folder: Optional[str] = None
    grandparent_folder: Optional[str] = None
    rel_path: Optional[str] = None
    accepted: Optional[bool] = None
    treatment: Optional[str] = None
    condition: Optional[str] = None
    date: Optional[str] = None

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
        
        Type conversion is derived from dataclass field annotations, so new fields
        are handled automatically. Unknown keys are ignored.
        
        Args:
            data: Dictionary containing RadonReport fields.
        
        Returns:
            RadonReport instance with values from the dictionary.
        """
        from typing import get_type_hints

        hints = get_type_hints(cls)
        known = {f.name for f in fields(cls)}

        def _is_none_or_nan(v: Any) -> bool:
            return v is None or (isinstance(v, float) and v != v)

        def _convert(value: Any, hint: Any) -> Any:
            if _is_none_or_nan(value):
                return None
            origin, args = get_origin(hint), get_args(hint)
            # Handle Optional / Union[X, None]
            if origin is not None and type(None) in args:
                inner = next((a for a in args if a is not type(None)), None)
                hint = inner if inner is not None else hint
            if hint is int:
                return int(value)
            if hint is float:
                return float(value)
            if hint is bool:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes")
                return bool(value)
            if hint is str:
                return str(value) if value is not None else None
            return value

        filtered: Dict[str, Any] = {}
        for key in known:
            if key not in data:
                continue
            value = data[key]
            hint = hints.get(key, Any)
            filtered[key] = _convert(value, hint) if not _is_none_or_nan(value) else None

        if "roi_id" not in filtered:
            raise ValueError("roi_id is required in RadonReport.from_dict()")

        return cls(**filtered)
