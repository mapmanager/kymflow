"""Kymograph ROI-based flow analysis.

This module provides KymAnalysis for managing ROIs and performing per-ROI
flow analysis on kymograph images. All analysis is ROI-based - each ROI
must be explicitly defined before analysis.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from kymflow.core.analysis.kym_flow_radon import FlowCancelled, mp_analyze_flow
from kymflow.core.analysis.utils import _medianFilter, _removeOutliers
from kymflow.core.metadata import AnalysisParameters
from kymflow.core.roi import clamp_coordinates, clamp_coordinates_to_size
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    from kymflow.core.image_loaders.acq_image import AcqImage

logger = get_logger(__name__)

ProgressCallback = Callable[[int, int], Any]
CancelCallback = Callable[[], bool]


class KymAnalysis:
    """Manages ROIs and performs flow analysis on kymograph images.
    
    KymAnalysis provides a unified API for managing ROIs and their associated
    analysis results. Each ROI is represented by an AnalysisParameters instance
    that includes both ROI coordinates and analysis metadata. When ROI coordinates
    change, analysis becomes invalid and must be re-run.
    
    Attributes:
        acq_image: Reference to the parent AcqImage (typically KymImage).
        _rois: Dictionary mapping roi_id to AnalysisParameters instances.
        _df: DataFrame containing all analysis results with 'roi_id' column.
        _dirty: Flag indicating if analysis needs to be saved.
        num_rois: Property returning the number of ROIs.
    """
    
    def __init__(
        self,
        acq_image: "AcqImage",
        *,
        load_analysis: bool = True,
    ) -> None:
        """Initialize KymAnalysis instance.
        
        Args:
            acq_image: Parent AcqImage instance (typically KymImage).
            load_analysis: If True, automatically load analysis from disk if available.
                Defaults to True.
        """
        self.acq_image = acq_image
        self._rois: Dict[int, AnalysisParameters] = {}
        self._df: Optional[pd.DataFrame] = None
        self._dirty: bool = False
        
        if load_analysis:
            self.load_analysis()
    
    def _invalidate_roi_analysis(self, roi: AnalysisParameters) -> None:
        """Invalidate analysis for an ROI.
        
        Helper method that clears all analysis-related fields from an ROI
        and removes its data from the analysis DataFrame.
        
        Args:
            roi: The ROI whose analysis should be invalidated.
        """
        roi.algorithm = ""
        roi.window_size = None
        roi.analyzed_at = None
        
        # Remove this ROI's data from DataFrame
        if self._df is not None and 'roi_id' in self._df.columns:
            self._df = self._df[self._df['roi_id'] != roi.roi_id].copy()
    
    def _filter_df_by_roi(self, df: pd.DataFrame, roi_id: int) -> pd.DataFrame:
        """Filter DataFrame to rows for a specific ROI.
        
        Args:
            df: DataFrame to filter.
            roi_id: ROI ID to filter by.
        
        Returns:
            Filtered DataFrame with only rows for the specified ROI.
        """
        if 'roi_id' not in df.columns:
            return pd.DataFrame()  # Return empty DataFrame if no roi_id column
        return df[df['roi_id'] == roi_id].copy()
    
    def _get_next_roi_id(self) -> int:
        """Get the next available ROI ID.
        
        Computes the next ID as max(existing_ids) + 1, or 1 if no ROIs exist.
        This ensures IDs are always unique and never reused.
        
        Returns:
            Next available ROI ID.
        """
        if not self._rois:
            return 1
        return max(self._rois.keys()) + 1
    
    @property
    def num_rois(self) -> int:
        """Number of ROIs in this analysis.
        
        Returns:
            Count of ROIs.
        """
        return len(self._rois)
    
    def _remove_roi_data_from_df(self, roi_id: int) -> None:
        """Remove all rows for a specific ROI from the analysis DataFrame.
        
        Helper method to centralize DataFrame filtering logic. If the DataFrame
        becomes empty after removal, sets it to None.
        
        Args:
            roi_id: ROI ID whose data should be removed.
        """
        if self._df is not None and 'roi_id' in self._df.columns:
            self._df = self._df[self._df['roi_id'] != roi_id].copy()
            # If DataFrame is now empty, set to None
            if len(self._df) == 0:
                self._df = None
    
    def _get_primary_path(self) -> Path | None:
        """Get the primary file path (first channel path).
        
        Returns:
            Path for the first channel, or None if no paths are set.
        """
        channel_keys = self.acq_image.getChannelKeys()
        if not channel_keys:
            # Try to get from _file_path_dict
            if hasattr(self.acq_image, '_file_path_dict') and self.acq_image._file_path_dict:
                return next(iter(self.acq_image._file_path_dict.values()))
            return None
        # Get path for first channel
        first_channel = min(channel_keys)
        return self.acq_image.getChannelPath(first_channel)
    
    def _get_analysis_folder_path(self) -> Path:
        """Get the analysis folder path for the acq_image.
        
        Pattern: parent folder + '-analysis' suffix
        Example: 20221102/Capillary1_0001.tif -> 20221102/20221102-analysis/
        
        Returns:
            Path to the analysis folder.
        """
        primary_path = self._get_primary_path()
        if primary_path is None:
            raise ValueError("No file path available for analysis folder")
        parent = primary_path.parent
        parent_name = parent.name
        analysis_folder_name = f"{parent_name}-analysis"
        return parent / analysis_folder_name
    
    def _get_save_paths(self) -> tuple[Path, Path]:
        """Get the save paths for analysis files.
        
        Returns:
            Tuple of (csv_path, json_path) for this acq_image's analysis.
        """
        analysis_folder = self._get_analysis_folder_path()
        primary_path = self._get_primary_path()
        if primary_path is None:
            raise ValueError("No file path available for save paths")
        base_name = primary_path.stem
        csv_path = analysis_folder / f"{base_name}.csv"
        json_path = analysis_folder / f"{base_name}.json"
        return csv_path, json_path
    
    def add_roi(
        self,
        left: Optional[int] = None,
        top: Optional[int] = None,
        right: Optional[int] = None,
        bottom: Optional[int] = None,
        note: str = "",
    ) -> AnalysisParameters:
        """Add a new ROI.
        
        Creates a new ROI with the specified coordinates. If coordinates are not
        specified, defaults to full image bounds. Coordinates are validated and
        clamped to image bounds. The ROI starts unanalyzed (analysis fields are None).
        
        Args:
            left: Left coordinate in full-image pixels. If None, defaults to 0.
            top: Top coordinate in full-image pixels. If None, defaults to 0.
            right: Right coordinate in full-image pixels. If None, defaults to image width.
            bottom: Bottom coordinate in full-image pixels. If None, defaults to image height.
            note: Optional note/description for this ROI.
        
        Returns:
            The newly created AnalysisParameters instance for this ROI.
        """
        roi_id = self._get_next_roi_id()
        
        # Get 2D image for clamping
        img = self.acq_image.get_img_slice(channel=1)
        img_h, img_w = img.shape
        
        # Default to full image bounds if coordinates not specified
        if left is None:
            left = 0
        if top is None:
            top = 0
        if right is None:
            right = img_w
        if bottom is None:
            bottom = img_h
        
        # Validate and clamp coordinates to image bounds
        left, top, right, bottom = clamp_coordinates(left, top, right, bottom, img)
        
        roi_params = AnalysisParameters(
            roi_id=roi_id,
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            note=note,
            # Analysis fields default to None/empty (unanalyzed)
        )
        
        self._rois[roi_id] = roi_params
        self._dirty = True
        return roi_params
    
    def delete_roi(self, roi_id: int) -> None:
        """Delete an ROI and its analysis.
        
        Removes the ROI from the collection and filters it out of the analysis DataFrame.
        
        Args:
            roi_id: Identifier of the ROI to delete.
        """
        if roi_id in self._rois:
            del self._rois[roi_id]
            self._remove_roi_data_from_df(roi_id)
            self._dirty = True
    
    def edit_roi(
        self,
        roi_id: int,
        *,
        left: Optional[float] = None,
        top: Optional[float] = None,
        right: Optional[float] = None,
        bottom: Optional[float] = None,
        note: Optional[str] = None,
    ) -> None:
        """Edit ROI coordinates or metadata.
        
        If coordinates (left/top/right/bottom) are changed, analysis becomes invalid
        (analysis fields set to None). If only note is changed, analysis remains valid.
        
        Args:
            roi_id: Identifier of the ROI to edit.
            left: New left coordinate (optional).
            top: New top coordinate (optional).
            right: New right coordinate (optional).
            bottom: New bottom coordinate (optional).
            note: New note (optional).
        
        Raises:
            ValueError: If roi_id is not found.
        """
        if roi_id not in self._rois:
            raise ValueError(f"ROI {roi_id} not found")
        
        roi = self._rois[roi_id]
        
        # Track if coordinates changed
        coords_changed = False
        if left is not None and left != roi.left:
            roi.left = left
            coords_changed = True
        if top is not None and top != roi.top:
            roi.top = top
            coords_changed = True
        if right is not None and right != roi.right:
            roi.right = right
            coords_changed = True
        if bottom is not None and bottom != roi.bottom:
            roi.bottom = bottom
            coords_changed = True
        
        # Validate and clamp coordinates
        if coords_changed:
            # Get 2D image for clamping
            img = self.acq_image.get_img_slice(channel=1)
            roi.left, roi.top, roi.right, roi.bottom = clamp_coordinates(
                roi.left, roi.top, roi.right, roi.bottom, img
            )
            
            # Invalidate analysis if coordinates changed
            self._invalidate_roi_analysis(roi)
        
        if note is not None:
            roi.note = note
        
        if coords_changed or note is not None:
            self._dirty = True
    
    def get_roi(self, roi_id: int) -> Optional[AnalysisParameters]:
        """Get ROI by ID.
        
        Args:
            roi_id: Identifier of the ROI to retrieve.
        
        Returns:
            AnalysisParameters instance for the ROI, or None if not found.
        """
        return self._rois.get(roi_id)
    
    def get_all_rois(self) -> List[AnalysisParameters]:
        """Get all ROIs in creation order.
        
        Returns:
            List of all AnalysisParameters instances.
        """
        return list(self._rois.values())
    
    def __iter__(self):
        """Make KymAnalysis iterable over its ROIs.
        
        Yields:
            AnalysisParameters instances for each ROI.
        """
        # Iterate over a copy of values to avoid modification during iteration issues
        yield from self._rois.values()
    
    def clear_all_rois(self) -> int:
        """Delete all ROIs and their analysis data.
        
        Removes all ROIs from the collection and clears their data from the
        analysis DataFrame. Resets the ROI ID counter to 1. Safe to call even
        if no ROIs exist (no-op).
        
        Returns:
            Number of ROIs that were deleted (0 if none existed).
        """
        # Early return if no ROIs to clear
        count = self.num_rois
        if count == 0:
            return 0
        
        roi_ids = list(self._rois.keys())
        self._rois.clear()
        
        # Remove all ROI data from DataFrame
        for roi_id in roi_ids:
            self._remove_roi_data_from_df(roi_id)
        
        self._dirty = True
        return count
    
    def analyze_roi(
        self,
        roi_id: int,
        window_size: int,
        *,
        progress_callback: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCallback] = None,
        use_multiprocessing: bool = True,
    ) -> None:
        """Run flow analysis on a specific ROI.
        
        Performs Radon-based flow analysis on the image region defined by the ROI
        coordinates. Results are stored in the analysis DataFrame with a 'roi_id'
        column. Analysis parameters are stored in the ROI's AnalysisParameters.
        
        Args:
            roi_id: Identifier of the ROI to analyze.
            window_size: Number of time lines per analysis window. Must be a multiple of 4.
            progress_callback: Optional callback function(completed, total) for progress.
            is_cancelled: Optional callback function() -> bool to check for cancellation.
            use_multiprocessing: If True, use multiprocessing for parallel computation.
        
        Raises:
            ValueError: If roi_id is not found or window_size is invalid.
            FlowCancelled: If analysis is cancelled via is_cancelled callback.
        """
        if roi_id not in self._rois:
            raise ValueError(f"ROI {roi_id} not found")
        
        channel = 1

        roi = self._rois[roi_id]
        
        # Extract image region based on ROI coordinates
        # ROI coordinates are already clamped to image bounds and properly ordered when added/edited
        image = self.acq_image.get_img_slice(channel=channel)
        
        # Convert ROI coordinates to pixel/line indices (already clamped and ordered)
        start_pixel = roi.top
        stop_pixel = roi.bottom
        start_line = roi.left
        stop_line = roi.right
        
        # Run analysis on the ROI region
        thetas, the_t, spread = mp_analyze_flow(
            image,
            window_size,
            space_dim=0,  # TODO: add api to get these from acq_image
            time_dim=1,
            start_pixel=start_pixel,
            stop_pixel=stop_pixel,
            start_line=start_line,
            stop_line=stop_line,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
            use_multiprocessing=use_multiprocessing,
        )
        
        # Store analysis parameters in ROI
        roi.algorithm = "mpRadon"
        roi.window_size = window_size
        roi.analyzed_at = datetime.now(timezone.utc)
        
        # Convert to physical units
        # For KymImage, voxels[0] is seconds_per_line, voxels[1] is um_per_pixel
        if self.acq_image.header.voxels is None or len(self.acq_image.header.voxels) < 2:
            raise ValueError("Image voxels not set or invalid for kymograph analysis")
        seconds_per_line = self.acq_image.header.voxels[0]
        um_per_pixel = self.acq_image.header.voxels[1]
        
        drew_time = the_t * seconds_per_line
        
        # Convert radians to angle and then to velocity
        _rad = np.deg2rad(thetas)
        drew_velocity = (um_per_pixel / seconds_per_line) * np.tan(_rad)
        drew_velocity = drew_velocity / 1000  # mm/s
        
        # Apply filtering
        clean_velocity = _removeOutliers(drew_velocity)
        clean_velocity = _medianFilter(clean_velocity, window_size=5)
        
        # Create DataFrame for this ROI's analysis
        primary_path = self._get_primary_path()
        parent_name = primary_path.parent.name if primary_path is not None else ""
        file_name = primary_path.name if primary_path is not None else ""
        
        # Get shape for numLines and pntsPerLine
        shape = self.acq_image.img_shape
        num_lines = shape[0] if shape is not None else 0
        pixels_per_line = shape[1] if shape is not None else 0
        
        roi_df = pd.DataFrame({
            "roi_id": roi_id,
            "time": drew_time,
            "velocity": drew_velocity,
            "parentFolder": parent_name,
            "file": file_name,
            "algorithm": "mpRadon",
            "delx": um_per_pixel,
            "delt": seconds_per_line,
            "numLines": num_lines,
            "pntsPerLine": pixels_per_line,
            "cleanVelocity": clean_velocity,
            "absVelocity": abs(clean_velocity),
        })
        
        # Append to main DataFrame (or create if first analysis)
        if self._df is None:
            self._df = roi_df
        else:
            # Remove old data for this ROI if it exists
            self._remove_roi_data_from_df(roi_id)
            # Append new data
            self._df = pd.concat([self._df, roi_df], ignore_index=True)
        
        self._dirty = True
    
    def save_analysis(self) -> bool:
        """Save analysis results to CSV and JSON files.
        
        Saves the analysis DataFrame (with all ROI analyses) to CSV and ROI data
        with analysis parameters to JSON. Only saves if dirty.
        
        Returns:
            True if analysis was saved successfully, False if no analysis exists
            or file is not dirty.
        """
        primary_path = self._get_primary_path()
        if primary_path is None:
            logger.warning("No path provided, analysis cannot be saved")
            return False
        
        if not self._dirty:
            logger.info(f"Analysis does not need to be saved for {primary_path.name}")
            return False
        
        if self._df is None or len(self._df) == 0:
            logger.warning(f"No analysis to save for {primary_path.name}")
            return False
        
        csv_path, json_path = self._get_save_paths()
        
        # Create analysis folder if it doesn't exist
        analysis_folder = csv_path.parent
        analysis_folder.mkdir(parents=True, exist_ok=True)
        
        # Save CSV
        self._df.to_csv(csv_path, index=False)
        logger.info(f"Saved analysis CSV to {csv_path}")
        
        # Prepare JSON data
        json_data = {
            "rois": [roi.to_dict() for roi in self._rois.values()],
        }
        
        # Save JSON
        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=2, default=str)
        logger.info(f"Saved analysis metadata to {json_path}")
        
        self._dirty = False
        return True
    
    def load_analysis(self) -> bool:
        """Load analysis results from CSV and JSON files.
        
        Loads the analysis DataFrame from CSV and restores ROIs with their
        analysis parameters from JSON.
        
        Returns:
            True if analysis was loaded successfully, False if files don't exist.
        """
        
        primary_path = self._get_primary_path()
        if primary_path is None:
            # logger.warning("No path provided, analysis cannot be loaded")
            return False
        
        csv_path, json_path = self._get_save_paths()
        
        if not csv_path.exists():
            # logger.info(f"No analysis CSV found for {self.kym_file.path.name}")
            return False
        
        if not json_path.exists():
            # logger.info(f"No analysis JSON found for {self.kym_file.path.name}")
            return False
        
        # Load CSV
        self._df = pd.read_csv(csv_path)
        
        # Load JSON
        with open(json_path, "r") as f:
            json_data = json.load(f)
        
        # Restore ROIs from JSON
        self._rois.clear()
        if "rois" in json_data:
            shape = self.acq_image.img_shape
            img_w = shape[1] if shape is not None else 0
            img_h = shape[0] if shape is not None else 0
            
            for roi_dict in json_data["rois"]:
                # Store original coordinates for validation (before filtering and clamping)
                original_left = roi_dict.get("left", 0)
                original_top = roi_dict.get("top", 0)
                original_right = roi_dict.get("right", 0)
                original_bottom = roi_dict.get("bottom", 0)
                
                # Use from_dict() to handle unknown field filtering, datetime conversion, and float->int conversion
                roi = AnalysisParameters.from_dict(roi_dict)
                
                # Validate and clamp ROI coordinates to image bounds
                # Store original coordinates for comparison (after from_dict conversion)
                original_roi = AnalysisParameters(
                    roi_id=roi.roi_id,
                    left=roi.left,
                    top=roi.top,
                    right=roi.right,
                    bottom=roi.bottom,
                    note=roi.note,
                    algorithm=roi.algorithm,
                    window_size=roi.window_size,
                    analyzed_at=roi.analyzed_at,
                )
                
                roi.left, roi.top, roi.right, roi.bottom = clamp_coordinates_to_size(
                    roi.left, roi.top, roi.right, roi.bottom, img_w, img_h
                )
                
                # Log warning if coordinates were modified
                if not roi.has_same_coordinates(original_roi):
                    logger.warning(
                        f"ROI {roi.roi_id} coordinates were clamped on load. "
                        f"Original: left={original_left}, top={original_top}, "
                        f"right={original_right}, bottom={original_bottom}. "
                        f"Clamped to: left={roi.left}, top={roi.top}, "
                        f"right={roi.right}, bottom={roi.bottom} "
                        f"(image size: {img_w}x{img_h}). "
                        f"If coordinates were changed, analysis may be invalid."
                    )
                    logger.warning(f'original_roi:{original_roi}')
                    logger.warning(f'roi:{roi}')
                    # Invalidate analysis if coordinates were changed
                    self._invalidate_roi_analysis(roi)
                
                self._rois[roi.roi_id] = roi
                # Note: _get_next_roi_id() will automatically compute correct next ID
        
        self._dirty = False
        return True
    
    def get_analysis(self, roi_id: Optional[int] = None) -> Optional[pd.DataFrame]:
        """Get analysis DataFrame, optionally filtered by ROI.
        
        Args:
            roi_id: If provided, return only data for this ROI. If None, return all data.
        
        Returns:
            DataFrame with analysis results, or None if no analysis exists.
        """
        if self._df is None:
            return None
        
        if roi_id is None:
            return self._df.copy()
        
        return self._filter_df_by_roi(self._df, roi_id)
    
    def get_analysis_value(
        self,
        roi_id: int,
        key: str,
        remove_outliers: bool = False,
        median_filter: int = 0,
    ) -> Optional[np.ndarray]:
        """Get a specific analysis value for an ROI.
        
        Args:
            roi_id: Identifier of the ROI.
            key: Column name to retrieve (e.g., "velocity", "time").
            remove_outliers: If True, remove outliers using 2*std threshold.
            median_filter: Median filter window size. 0 = disabled, >0 = enabled (must be odd).
        
        Returns:
            Array of values for the specified key, or None if not found.
        """
        roi_df = self.get_analysis(roi_id=roi_id)
        if roi_df is None:
            logger.warning(f"No analysis found for ROI {roi_id}, requested key was:{key}")
            return None
        
        if key not in roi_df.columns:
            logger.warning(f"Key {key} not found in analysis DataFrame for ROI {roi_id}")
            return None
        
        values = roi_df[key].values
        if remove_outliers:
            values = _removeOutliers(values)
        if median_filter > 0:
            values = _medianFilter(values, median_filter)
        return values
    
    def has_analysis(self, roi_id: Optional[int] = None) -> bool:
        """Check if analysis exists.
        
        Args:
            roi_id: If provided, check if this specific ROI has analysis.
                If None, check if any ROI has analysis.
        
        Returns:
            True if analysis exists, False otherwise.
        """
        if roi_id is None:
            return self._df is not None and len(self._df) > 0
        
        if roi_id not in self._rois:
            return False
        
        roi = self._rois[roi_id]
        return roi.analyzed_at is not None
    
    def __str__(self) -> str:
        """String representation."""
        return f"KymAnalysis(rois={list(self._rois.keys()) if self._rois else []})"
