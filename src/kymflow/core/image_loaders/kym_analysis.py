"""Kymograph ROI-based flow analysis.

This module provides KymAnalysis for managing ROIs and performing per-ROI
flow analysis on kymograph images. All analysis is ROI-based - each ROI
must be explicitly defined before analysis.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import queue
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, TypedDict
from uuid import uuid4

import numpy as np
import pandas as pd

from kymflow.core.analysis.kym_flow_radon import mp_analyze_flow
from kymflow.core.analysis.utils import _medianFilter, _removeOutliers_sd, _removeOutliers_analyzeflow
from kymflow.core.utils.logging import get_logger

# DEPRECATED: Stall analysis is deprecated
# from kymflow.core.analysis.stall_analysis import StallAnalysis, StallAnalysisParams
from kymflow.core.analysis.velocity_events.velocity_events import (
    UserType,
    VelocityEvent,
    detect_events,
    time_to_index,
)

if TYPE_CHECKING:
    from kymflow.core.image_loaders.acq_image import AcqImage

logger = get_logger(__name__)

# Temporary diagnostics to trace GUI imports during spawn
def _check_gui_imports(context: str) -> None:
    """Check if GUI modules are imported at this point.
    
    This is temporary diagnostic logging to identify import chains that pull
    in GUI code during multiprocessing worker spawn.
    
    Args:
        context: Description of where this check is happening (e.g., "module import").
    """
    process_name = mp.current_process().name
    pid = os.getpid()
    module_name = __name__
    
    has_gui_v2 = 'kymflow.gui_v2' in sys.modules
    has_nicegui = 'nicegui' in sys.modules
    gui_modules = [m for m in sys.modules.keys() if 'gui' in m.lower() or 'nicegui' in m.lower()]
    
    if has_gui_v2 or has_nicegui or gui_modules:
        logger.warning(
            f"GUI MODULES DETECTED [{context}]: "
            f"pid={pid}, process={process_name}, module={module_name}, "
            f"gui_v2={has_gui_v2}, nicegui={has_nicegui}, modules={gui_modules}"
        )
    else:
        logger.debug(
            f"No GUI modules detected [{context}]: "
            f"pid={pid}, process={process_name}, module={module_name}"
        )

# Check on module import
# _check_gui_imports("kym_analysis module import")

CancelCallback = Callable[[], bool]


@dataclass
class RoiAnalysisMetadata:
    """Analysis metadata for a specific ROI.

    ROI geometry (dim0_start/dim0_stop/dim1_start/dim1_stop, channel, z) lives in AcqImage.rois.
    This stores only analysis state/results metadata.
    """

    roi_id: int
    algorithm: str = "mpRadon"
    window_size: int | None = None
    analyzed_at: str | None = None  # ISO-8601 UTC string
    roi_revision_at_analysis: int = 0


class VelocityReportRow(TypedDict):
    event_id: str
    roi_id: int
    path: Optional[str]
    event_type: str
    i_start: int
    t_start: float
    i_peak: Optional[int]
    t_peak: Optional[float]
    i_end: Optional[int]
    t_end: Optional[float]
    score_peak: Optional[float]
    baseline_before: Optional[float]
    baseline_after: Optional[float]
    strength: Optional[float]
    nan_fraction_in_event: Optional[float]
    n_valid_in_event: Optional[int]
    duration_sec: Optional[float]
    machine_type: str
    user_type: str
    note: str


class KymAnalysis:
    """Manages ROIs and performs flow analysis on kymograph images.
    
    KymAnalysis provides a unified API for managing ROIs and their associated
    analysis results. ROI geometry lives in AcqImage.rois; KymAnalysis stores
    only analysis state/results metadata. When ROI coordinates change, analysis
    becomes invalid and must be re-run.
    
    Attributes:
        acq_image: Reference to the parent AcqImage (typically KymImage).
        _analysis_metadata: Dictionary mapping roi_id to RoiAnalysisMetadata instances.
        _df: DataFrame containing all analysis results with 'roi_id' column.
        _dirty: Flag indicating if analysis needs to be saved.
        num_rois: Property returning the number of ROIs.
    """
    
    def __init__(
        self,
        acq_image: "AcqImage",
    ) -> None:
        """Initialize KymAnalysis instance.
        
        Automatically attempts to load analysis from disk if available.
        If path is None or files don't exist, analysis remains empty.
        
        Args:
            acq_image: Parent AcqImage instance (typically KymImage).
        """
        self.acq_image = acq_image
        # ROI geometry lives in acq_image.rois; KymAnalysis stores only analysis state/results.
        self._analysis_metadata: Dict[int, RoiAnalysisMetadata] = {}
        self._df: Optional[pd.DataFrame] = None
        self._dirty: bool = False
        # DEPRECATED: Stall analysis is deprecated
        # self._stall_analysis: Dict[int, StallAnalysis] = {}
        # Stall analysis is computed on-demand from stored analysis values (e.g., velocity).
        self._velocity_events: Dict[int, List[VelocityEvent]] = {}
        # Velocity events are computed on-demand from stored analysis values (e.g., velocity).
        
        # Runtime-only UUID mapping for stable event_id (not serialized)
        # Maps: uuid -> (roi_id, index_in_list)
        self._velocity_event_uuid_map: Dict[str, Tuple[int, int]] = {}
        # Reverse mapping for O(1) lookup: (roi_id, index) -> uuid
        self._velocity_event_uuid_reverse: Dict[Tuple[int, int], str] = {}
        
        # Always try to load analysis (handles path=None gracefully)
        self.load_analysis()
    
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
    
    @property
    def num_rois(self) -> int:
        """Number of ROIs on the parent image (single source of truth)."""
        return self.acq_image.rois.numRois()

    def has_analysis(self, roi_id: int | None = None) -> bool:
        """Return True if analysis exists for any ROI (or for a specific ROI)."""
        if roi_id is None:
            return bool(self._analysis_metadata)
        return roi_id in self._analysis_metadata

    @property
    def is_dirty(self) -> bool:
        """Return True if analysis or metadata/ROI changes are unsaved."""
        return self._dirty or self.acq_image.is_metadata_dirty

    def get_analysis_metadata(self, roi_id: int) -> RoiAnalysisMetadata | None:
        """Return analysis metadata for roi_id, or None if not analyzed."""
        return self._analysis_metadata.get(roi_id)

    def is_stale(self, roi_id: int) -> bool:
        """Return True if roi_id is missing analysis or ROI has changed since analysis."""
        roi = self.acq_image.rois.get(roi_id)
        if roi is None:
            return True
        meta = self._analysis_metadata.get(roi_id)
        if meta is None:
            return True
        return roi.revision != meta.roi_revision_at_analysis

    def invalidate(self, roi_id: int) -> None:
        """Drop analysis (df rows + metadata) for a specific ROI."""
        self._analysis_metadata.pop(roi_id, None)
        self._remove_roi_data_from_df(roi_id)
        self._dirty = True
    
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
        """Get the primary file path (representative path from any channel).
        
        Returns:
            Representative path from acq_image, or None if no path available.
        """
        return self.acq_image.path
    
    def _get_analysis_folder_path(self) -> Path:
        """Get the analysis folder path for the acq_image.
        
        Pattern: fixed folder name under the parent directory.
        Example: 20221102/Capillary1_0001.tif -> 20221102/flow-analysis/
        
        Returns:
            Path to the analysis folder.
        """
        primary_path = self._get_primary_path()
        if primary_path is None:
            raise ValueError("No file path available for analysis folder")
        return primary_path.parent / "flow-analysis"
    
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
        csv_path = analysis_folder / f"{base_name}_kymanalysis.csv"
        json_path = analysis_folder / f"{base_name}_kymanalysis.json"
        return csv_path, json_path
    
    def analyze_roi(
        self,
        roi_id: int,
        window_size: int,
        *,
        progress_queue: Optional[queue.Queue] = None,
        is_cancelled: Optional[CancelCallback] = None,
        use_multiprocessing: bool = True,
    ) -> None:
        """Run flow analysis on a specific ROI.
        
        Performs Radon-based flow analysis on the image region defined by the ROI
        coordinates. Results are stored in the analysis DataFrame with a 'roi_id'
        column. Analysis metadata is stored in RoiAnalysisMetadata.
        
        Args:
            roi_id: Identifier of the ROI to analyze.
            window_size: Number of time lines per analysis window. Must be a multiple of 4.
            progress_queue: Optional queue to receive progress messages from the
                parent process as tuples of the form ('progress', completed, total).
                This is safe to consume from GUI/main threads. Progress is emitted
                from the parent process only, never from worker processes.
            is_cancelled: Optional callback function() -> bool to check for cancellation.
            use_multiprocessing: If True, use multiprocessing for parallel computation.
        
        Raises:
            ValueError: If roi_id is not found or window_size is invalid.
            FlowCancelled: If analysis is cancelled via is_cancelled callback.
        """
        roi = self.acq_image.rois.get(roi_id)
        if roi is None:
            raise ValueError(f"ROI {roi_id} not found")

        channel = roi.channel
        
        # Extract image region based on ROI coordinates
        # ROI coordinates are already clamped to image bounds and properly ordered when added/edited
        image = self.acq_image.get_img_slice(channel=channel)
        
        # Convert ROI coordinates to pixel/line indices (already clamped and ordered)
        # For kymographs: dim0 = time (rows), dim1 = space (columns)
        start_pixel = roi.bounds.dim0_start  # time dimension (rows)
        stop_pixel = roi.bounds.dim0_stop    # time dimension (rows)
        start_line = roi.bounds.dim1_start    # space dimension (columns)
        stop_line = roi.bounds.dim1_stop      # space dimension (columns)
        
        # logger.info(f'calling mp_analyze_flow() with roi {roi_id}:')
        # print(roi)
        
        # Temporary diagnostic: check GUI imports before calling mp_analyze_flow
        # _check_gui_imports(f"analyze_roi before mp_analyze_flow (roi_id={roi_id})")
        
        # Run analysis on the ROI region
        # mp_analyze_flow expects explicit dim0/dim1 bounds in the (time, space) convention.
        thetas, the_t, spread = mp_analyze_flow(
            image,
            window_size,
            start_pixel,
            stop_pixel,
            start_line,
            stop_line,
            progress_queue=progress_queue,
            is_cancelled=is_cancelled,
            use_multiprocessing=use_multiprocessing,
            verbose=False,
        )
        
        # Record analysis metadata (geometry lives in acq_image.rois)
        self._analysis_metadata[roi_id] = RoiAnalysisMetadata(
            roi_id=roi_id,
            algorithm="mpRadon",
            window_size=window_size,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            roi_revision_at_analysis=roi.revision,
        )
        
        # Convert to physical units using KymImage properties
        # KymImage knows which dimension is which
        seconds_per_line = self.acq_image.seconds_per_line
        um_per_pixel = self.acq_image.um_per_pixel
        
        drew_time = the_t * seconds_per_line
        
        # Convert radians to angle and then to velocity
        _rad = np.deg2rad(thetas)
        drew_velocity = (um_per_pixel / seconds_per_line) * np.tan(_rad)
        drew_velocity = drew_velocity / 1000  # mm/s
        
        # Apply filtering
        clean_velocity = _removeOutliers_sd(drew_velocity)
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
            "channel": roi.channel,
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
        with analysis parameters to JSON. Also saves ROIs and metadata via AcqImage.
        Only saves if dirty.
        
        Returns:
            True if analysis was saved successfully, False if no analysis exists
            or file is not dirty.
        """
        primary_path = self._get_primary_path()
        if primary_path is None:
            logger.warning("No path provided, analysis cannot be saved")
            return False

        if not self.is_dirty:
            logger.info(f"Analysis does not need to be saved for {primary_path.name}")
            return False

        # Save ROIs and metadata first (ensures ROIs are persisted)
        # This saves header, experiment_metadata, and ROIs to metadata.json
        metadata_saved = self.acq_image.save_metadata()
        if not metadata_saved:
            logger.warning("Failed to save metadata (ROIs), but continuing with analysis save")

        analysis_saved = False
        if self._df is not None and len(self._df) > 0:
            csv_path, json_path = self._get_save_paths()

            # Create analysis folder if it doesn't exist
            analysis_folder = csv_path.parent
            analysis_folder.mkdir(parents=True, exist_ok=True)

            # Save CSV
            self._df.to_csv(csv_path, index=False)

            # logger.info(f"Saved analysis CSV to {csv_path}")

            # Reconcile to current ROIs (single source of truth)
            current_roi_ids = {roi.id for roi in self.acq_image.rois}
            if self._df is not None and 'roi_id' in self._df.columns:
                self._df = self._df[self._df['roi_id'].isin(current_roi_ids)].copy()
            self._analysis_metadata = {
                rid: meta for rid, meta in self._analysis_metadata.items() if rid in current_roi_ids
            }

            # Prepare JSON data (analysis metadata only; no ROI geometry)
            json_data = {
                "version": "2.0",
                "analysis_metadata": {
                    str(rid): {
                        "roi_id": meta.roi_id,
                        "algorithm": meta.algorithm,
                        "window_size": meta.window_size,
                        "analyzed_at": meta.analyzed_at,
                        "roi_revision_at_analysis": meta.roi_revision_at_analysis,
                    }
                    for rid, meta in self._analysis_metadata.items()
                },
                # DEPRECATED: Stall analysis is deprecated
                # "stall_analysis": {
                #     str(rid): sa.to_dict() for rid, sa in self._stall_analysis.items()
                # },
                "velocity_events": {
                    str(rid): [ev.to_dict() for ev in evs]
                    for rid, evs in self._velocity_events.items()
                },
            }

            # Save JSON
            with open(json_path, "w") as f:
                json.dump(json_data, f, indent=2, default=str)

            # logger.info(f"Saved analysis metadata to {json_path}")

            self._dirty = False
            analysis_saved = True
        elif self._dirty:
            logger.info("Analysis dirty but no analysis data to save for %s", primary_path.name)

        return metadata_saved or analysis_saved
    
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
            # if primary_path:
            #     logger.info(f"No analysis CSV found for {primary_path.name}")
            # else:
            #     logger.info("No analysis CSV found (no path available)")
            # logger.info(f"  csv_path:{csv_path}")
            return False
        
        if not json_path.exists():
            # if primary_path:
            #     logger.info(f"No analysis JSON found for {primary_path.name}")
            # else:
            #     logger.info("No analysis JSON found (no path available)")
            # logger.info(f"  json_path:{json_path}")
            return False
        
        # Load CSV
        self._df = pd.read_csv(csv_path)
        
        # Load JSON
        with open(json_path, "r") as f:
            json_data = json.load(f)
        
        # Load analysis metadata (v2.0 only). We do not recreate ROIs here.
        version = str(json_data.get("version", ""))
        if not version.startswith("2.") or "analysis_metadata" not in json_data:
            logger.warning(
                f"Unsupported analysis JSON schema for {primary_path.name}. "
                "Expected version starting with '2.' and key 'analysis_metadata'."
            )
            return False

        self._analysis_metadata.clear()
        for key, meta in json_data.get("analysis_metadata", {}).items():
            try:
                roi_id = int(meta.get("roi_id", key))
                self._analysis_metadata[roi_id] = RoiAnalysisMetadata(
                    roi_id=roi_id,
                    algorithm=str(meta.get("algorithm", "mpRadon")),
                    window_size=meta.get("window_size"),
                    analyzed_at=meta.get("analyzed_at"),
                    roi_revision_at_analysis=int(meta.get("roi_revision_at_analysis", 0)),
                )
            except Exception as e:
                logger.warning(f"Skipping invalid analysis metadata entry {key}: {e}")

        # DEPRECATED: Stall analysis is deprecated
        # # Load stall analysis (optional; may be absent in older analysis JSON).
        # self._stall_analysis.clear()
        # for roi_id_str, payload in json_data.get("stall_analysis", {}).items():
        #     try:
        #         roi_id = int(roi_id_str)
        #         self._stall_analysis[roi_id] = StallAnalysis.from_dict(payload)
        #     except Exception as e:
        #         logger.warning(f"Skipping invalid stall_analysis entry {roi_id_str}: {e}")

        # Load velocity events (optional; may be absent in older analysis JSON).
        self._velocity_events.clear()
        self._velocity_event_uuid_map.clear()
        self._velocity_event_uuid_reverse.clear()
        for roi_id_str, events_list in json_data.get("velocity_events", {}).items():
            try:
                roi_id = int(roi_id_str)
                events = [
                    VelocityEvent.from_dict(ev_dict) for ev_dict in events_list
                ]
                self._velocity_events[roi_id] = events
                # Generate stable UUIDs for each event on load
                for idx, _ in enumerate(events):
                    uuid = str(uuid4())
                    self._velocity_event_uuid_map[uuid] = (roi_id, idx)
                    self._velocity_event_uuid_reverse[(roi_id, idx)] = uuid
            except Exception as e:
                logger.warning(f"Skipping invalid velocity_events entry {roi_id_str}: {e}")

        # Reconcile to current ROIs
        current_roi_ids = {roi.id for roi in self.acq_image.rois}
        self._analysis_metadata = {
            rid: meta for rid, meta in self._analysis_metadata.items() if rid in current_roi_ids
        }
        # DEPRECATED: Stall analysis is deprecated
        # self._stall_analysis = {
        #     rid: sa for rid, sa in self._stall_analysis.items() if rid in current_roi_ids
        # }
        # Remove events for deleted ROIs and clean up UUID mappings
        removed_roi_ids = set(self._velocity_events.keys()) - current_roi_ids
        for removed_roi_id in removed_roi_ids:
            events = self._velocity_events.get(removed_roi_id, [])
            for idx in range(len(events)):
                uuid_key = (removed_roi_id, idx)
                if uuid_key in self._velocity_event_uuid_reverse:
                    uuid = self._velocity_event_uuid_reverse.pop(uuid_key)
                    if uuid in self._velocity_event_uuid_map:
                        del self._velocity_event_uuid_map[uuid]
        self._velocity_events = {
            rid: evs for rid, evs in self._velocity_events.items() if rid in current_roi_ids
        }
        if self._df is not None and 'roi_id' in self._df.columns:
            self._df = self._df[self._df['roi_id'].isin(current_roi_ids)].copy()
        
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
            remove_outliers: If True, remove outliers using old v0 flowanalysis with _removeOutliers_analyzeflow.
            median_filter: Median filter window size. 0 = disabled, >0 = enabled (must be odd).
        
        Returns:
            Array of values for the specified key, or None if not found.
        """

        roi_df = self.get_analysis(roi_id=roi_id)
        
        # logger.info('roi_df:')
        # print(roi_df)

        if roi_df is None:
            logger.warning(f"No analysis found for ROI {roi_id}, requested key was:{key}")
            return None
        
        if key not in roi_df.columns:
            logger.warning(f"Key {key} not found in analysis DataFrame for ROI {roi_id}")
            return None
        
        values = roi_df[key].values

        # logger.info(f'values: key:{key} n:{len(values)} min:{np.min(values)}, max:{np.max(values)}')
        # print(values)

        # newer version
        # if remove_outliers:
        #     values = _removeOutliers_sd(values)
        #     # set to np.nan if values[i] < 100000
        #     values[values < -100000] = np.nan

        # older version
        if remove_outliers:
            values = _removeOutliers_analyzeflow(values)

        if median_filter > 0:
            values = _medianFilter(values, median_filter)
        
        return values
    

    # DEPRECATED: Stall analysis is deprecated
    # def run_stall_analysis(self, roi_id: int, params: StallAnalysisParams) -> StallAnalysis:
    #     """Run stall analysis for a single ROI and store results.
    #
    #     This method is intentionally **on-demand**: it does not run automatically
    #     when flow analysis is computed. A caller (GUI/script) supplies parameters and
    #     explicitly requests stall detection once the underlying analysis values exist.
    #
    #     The source signal is selected via `params.velocity_key` (e.g. 'velocity',
    #     'cleanVelocity', 'signedVelocity').
    #
    #     Args:
    #         roi_id: Identifier of the ROI to analyze.
    #         params: Stall analysis parameters.
    #
    #     Returns:
    #         The computed `StallAnalysis` instance.
    #
    #     Raises:
    #         ValueError: If the requested analysis values are missing for this ROI.
    #     """
    #     values = self.get_analysis_value(
    #         roi_id=roi_id,
    #         key=params.velocity_key,
    #         remove_outliers=False,
    #     )
    #     if values is None:
    #         raise ValueError(
    #             f"Cannot run stall analysis: ROI {roi_id} has no analysis values for key '{params.velocity_key}'."
    #         )
    #
    #     analysis = StallAnalysis.run(velocity=values, params=params)
    #     self._stall_analysis[roi_id] = analysis
    #     # Mark dirty so callers know there are unsaved results.
    #     self._dirty = True
    #     return analysis
    #
    # def get_stall_analysis(self, roi_id: int) -> Optional[StallAnalysis]:
    #     """Return stall analysis results for roi_id, or None if not present.
    #
    #     Args:
    #         roi_id: Identifier of the ROI.
    #
    #     Returns:
    #         Stored `StallAnalysis` results, or None if stall analysis has not been run
    #         for this ROI (or results were not loaded).
    #     """
    #     return self._stall_analysis.get(roi_id)

    def run_velocity_event_analysis(
        self,
        roi_id: int,
        *,
        velocity_key: str = "velocity",
        remove_outliers: bool = False,
        **detect_events_kwargs: Any,
    ) -> list[VelocityEvent]:
        """Run velocity event detection for a single ROI and store results.

        This method is intentionally **on-demand**: it does not run automatically
        when flow analysis is computed. A caller (GUI/script) explicitly requests
        event detection once the underlying analysis values exist.

        The source signal is selected via `velocity_key` (e.g. 'velocity',
        'cleanVelocity', 'absVelocity').

        Args:
            roi_id: Identifier of the ROI to analyze.
            velocity_key: Column name to retrieve from analysis (default: "velocity").
            remove_outliers: If True, remove outliers using 2*std threshold before detection.
            **detect_events_kwargs: Additional keyword arguments passed to detect_events()
                (e.g., win_cmp_sec, mad_k, top_k_total, etc.).

        Returns:
            List of detected VelocityEvent instances.

        Raises:
            ValueError: If the requested analysis values are missing for this ROI.
        """
        # Get velocity values
        velocity = self.get_analysis_value(
            roi_id=roi_id,
            key=velocity_key,
            remove_outliers=remove_outliers,
        )
        if velocity is None:
            raise ValueError(
                f"Cannot run velocity event analysis: ROI {roi_id} has no analysis values for key '{velocity_key}'."
            )

        # explicitly remove outlierss like old v0 flowanalysis
        # velocity = _removeOutliers_analyzeflow(velocity)
        
        # Get time values (required for detect_events)
        time_s = self.get_analysis_value(
            roi_id=roi_id,
            key="time",
            # remove_outliers=False,
        )
        if time_s is None:
            raise ValueError(
                f"Cannot run velocity event analysis: ROI {roi_id} has no 'time' values."
            )

        # Run detection
        events, _debug = detect_events(time_s, velocity, **detect_events_kwargs)
        
        # Store results, if we had previous roi_id velocity events -> THIS REPLACES ALL OF THEM
        #self._velocity_events[roi_id] = events
        
        # remove existing events (do not remove 'user added' or true_stall)
        _nBefore = self.num_velocity_events(roi_id)
        
        self.remove_velocity_event(roi_id, "auto_detected")
        
        _nAfter = self.num_velocity_events(roi_id)
        
        logger.info(f"roi:{roi_id} _nBefore:{_nBefore} _nAfter:{_nAfter} removed:{_nBefore - _nAfter}")

        # append detected event
        self._velocity_events[roi_id] = self._velocity_events[roi_id] + events

        # Mark dirty so callers know there are unsaved results.
        self._dirty = True
        return events

    def remove_velocity_event(self, roi_id:int, remove_these:str) -> None:
        """Remove velocity events by 'Type' and 'User Type'

        Args:
            roi_id: Identifier of the ROI.
            remove_these:
                "_remove_all" to remove all events
                "auto_detected" removes only auto-detected events (keeps user-added and reviewed events)
        
        For "auto_detected" mode:
            **What is kept (not removed):**
            - Events with event_type == "User Added" (regardless of user_type)
            - Events with user_type != "unreviewed" (regardless of event_type)
            
            **What is removed:**
            - Events that are NOT "User Added" AND have user_type == "unreviewed"
            - In other words: auto-detected events that haven't been reviewed yet
            
            This allows removing only the automatically detected events while preserving:
            - All user-added events
            - All events that have been reviewed/classified by the user
        """
        if remove_these == "_remove_all":
            self._velocity_events[roi_id] = []
        elif remove_these == "auto_detected":
            # Keep events that are "User Added" OR have user_type != "unreviewed"
            # Remove events that are NOT "User Added" AND have user_type == "unreviewed"
            self._velocity_events[roi_id] = [
                event
                for event in self._velocity_events[roi_id]
                if event.event_type == "User Added" or event.user_type != "unreviewed"
            ]
        else:
            raise ValueError(f"Invalid remove_these value: {remove_these}")
        self._dirty = True

    def num_velocity_events(self, roi_id: int) -> int:
        """Return the number of velocity events for roi_id.

        Args:
            roi_id: Identifier of the ROI.

        Returns:
            Number of velocity events for the ROI.
        """
        return len(self._velocity_events.get(roi_id, []))

    def total_num_velocity_events(self) -> int:
        """Return the total number of velocity events across all ROIs.

        Returns:
            Total number of velocity events across all ROIs.
        """
        return sum(len(events) for events in self._velocity_events.values())

    def get_velocity_events(self, roi_id: int) -> Optional[list[VelocityEvent]]:
        """Return velocity event results for roi_id, or None if not present.

        Args:
            roi_id: Identifier of the ROI.

        Returns:
            Stored list of VelocityEvent instances, or None if velocity event analysis
            has not been run for this ROI (or results were not loaded).
        """
        return self._velocity_events.get(roi_id)

    def _velocity_event_id(self, roi_id: int, event: VelocityEvent) -> str:
        """Generate a stable event_id for a velocity event.
        
        DEPRECATED: This method is kept for backward compatibility but is no longer
        used for event identification. Events now use UUID-based event_id.
        """
        i_end_value = event.i_end if event.i_end is not None else "None"
        return f"{roi_id}:{event.i_start}:{i_end_value}:{event.event_type}"

    def _find_event_by_uuid(self, event_id: str) -> tuple[int, int, VelocityEvent] | None:
        """Find event by UUID event_id.
        
        Returns:
            Tuple of (roi_id, index, event) if found, None otherwise.
        """
        if event_id not in self._velocity_event_uuid_map:
            return None
        roi_id, index = self._velocity_event_uuid_map[event_id]
        events = self._velocity_events.get(roi_id)
        if events is None or index >= len(events):
            # Clean up stale mapping
            del self._velocity_event_uuid_map[event_id]
            if (roi_id, index) in self._velocity_event_uuid_reverse:
                del self._velocity_event_uuid_reverse[(roi_id, index)]
            return None
        return (roi_id, index, events[index])

    def update_velocity_event_field(self, event_id: str, field: str, value: Any) -> str | None:
        """Update a field on a velocity event by event_id.

        Returns:
            New event_id if an event was updated, None if not found or invalid.
        """
        if field not in {"user_type", "t_start", "t_end"}:
            logger.warning('Unsupported velocity event update field: "%s"', field)
            logger.warning("  event_id: %s", event_id)
            logger.warning("  field: %s", field)
            logger.warning("  value: %s", value)
            return None

        new_user_type: UserType | None = None
        new_t_start: float | None = None
        new_t_end: float | None = None
        if field == "user_type":
            try:
                new_user_type = UserType(str(value))
            except Exception as exc:
                logger.warning("Invalid user_type value %r: %s", value, exc)
                return None
        elif field == "t_start":
            try:
                new_t_start = float(value)
            except Exception as exc:
                logger.warning("Invalid t_start value %r: %s", value, exc)
                return None
        elif field == "t_end":
            if value is None:
                new_t_end = None
            else:
                try:
                    new_t_end = float(value)
                except Exception as exc:
                    logger.warning("Invalid t_end value %r: %s", value, exc)
                    return None

        # Find event by UUID
        result = self._find_event_by_uuid(event_id)
        if result is None:
            return None
        roi_id, idx, event = result
        
        seconds_per_line = float(self.acq_image.seconds_per_line)
        if field == "user_type":
            events = self._velocity_events[roi_id]
            events[idx] = replace(event, user_type=new_user_type)
            self._velocity_events[roi_id] = events
        elif field == "t_start":
            new_i_start = time_to_index(new_t_start, seconds_per_line)
            new_duration = (
                float(event.t_end) - float(new_t_start)
                if event.t_end is not None
                else None
            )
            events = self._velocity_events[roi_id]
            events[idx] = replace(
                event,
                t_start=new_t_start,
                i_start=new_i_start,
                duration_sec=new_duration,
            )
            self._velocity_events[roi_id] = events
        elif field == "t_end":
            new_i_end = (
                None
                if new_t_end is None
                else time_to_index(new_t_end, seconds_per_line)
            )
            new_duration = (
                None
                if new_t_end is None
                else float(new_t_end) - float(event.t_start)
            )
            events = self._velocity_events[roi_id]
            events[idx] = replace(
                event,
                t_end=new_t_end,
                i_end=new_i_end,
                duration_sec=new_duration,
            )
            self._velocity_events[roi_id] = events
        
        self._dirty = True
        # UUID doesn't change, return same event_id
        return event_id

    def update_velocity_event_range(self, event_id: str, t_start: float, t_end: float | None) -> str | None:
        """Update both t_start and t_end atomically to avoid event_id mismatch.

        When updating both t_start and t_end, the event_id changes after the first update,
        causing the second update to fail. This method updates both in a single operation.

        Returns:
            New event_id if an event was updated, None if not found or invalid.
        """
        try:
            new_t_start = float(t_start)
            new_t_end = float(t_end) if t_end is not None else None
        except (ValueError, TypeError) as exc:
            logger.warning("Invalid t_start/t_end values: %s", exc)
            return False

        # Find event by UUID
        result = self._find_event_by_uuid(event_id)
        if result is None:
            return None
        roi_id, idx, event = result
        
        seconds_per_line = float(self.acq_image.seconds_per_line)
        new_i_start = time_to_index(new_t_start, seconds_per_line)
        new_i_end = (
            None
            if new_t_end is None
            else time_to_index(new_t_end, seconds_per_line)
        )
        new_duration = (
            None
            if new_t_end is None
            else float(new_t_end) - float(new_t_start)
        )
        events = self._velocity_events[roi_id]
        events[idx] = replace(
            event,
            t_start=new_t_start,
            i_start=new_i_start,
            t_end=new_t_end,
            i_end=new_i_end,
            duration_sec=new_duration,
        )
        self._velocity_events[roi_id] = events
        self._dirty = True
        # UUID doesn't change, return same event_id
        return event_id

    def add_velocity_event(
        self, roi_id: int, t_start: float, t_end: float | None = None
    ) -> str:
        """Add a new velocity event for the specified ROI.

        Creates a new VelocityEvent with the given t_start/t_end. Other fields
        are set to defaults (event_type="baseline_drop", user_type=UNREVIEWED, etc.).
        The event is appended to the ROI's event list. Future TODO: sort events by t_start.

        Args:
            roi_id: Identifier of the ROI.
            t_start: Event start time in seconds.
            t_end: Event end time in seconds, or None.

        Returns:
            The generated event_id string for the new event.

        Raises:
            ValueError: If roi_id is not found or t_start is invalid.
        """
        roi = self.acq_image.rois.get(roi_id)
        if roi is None:
            raise ValueError(f"ROI {roi_id} not found")

        seconds_per_line = float(self.acq_image.seconds_per_line)
        i_start = time_to_index(t_start, seconds_per_line)

        i_end: int | None = None
        duration_sec: float | None = None
        if t_end is not None:
            i_end = time_to_index(t_end, seconds_per_line)
            duration_sec = float(t_end - t_start)

        # Create new event with defaults
        new_event = VelocityEvent(
            # event_type="baseline_drop",  # Default event type
            event_type="User Added",  # Default event type
            i_start=i_start,
            t_start=t_start,
            i_end=i_end,
            t_end=t_end,
            duration_sec=duration_sec,
            user_type=UserType.UNREVIEWED,  # Default user type
        )

        # Append to the ROI's event list
        if roi_id not in self._velocity_events:
            self._velocity_events[roi_id] = []
        self._velocity_events[roi_id].append(new_event)
        
        # Generate UUID for the new event and add to mappings
        idx = len(self._velocity_events[roi_id]) - 1  # Index of the newly appended event
        event_uuid = str(uuid4())
        self._velocity_event_uuid_map[event_uuid] = (roi_id, idx)
        self._velocity_event_uuid_reverse[(roi_id, idx)] = event_uuid

        # Mark dirty
        self._dirty = True

        # Return UUID event_id (not the old format)
        return event_uuid

    def delete_velocity_event(self, event_id: str) -> bool:
        """Delete a velocity event by UUID event_id.

        Args:
            event_id: UUID string to delete.

        Returns:
            True if an event was deleted, False if not found.
        """
        # Find event by UUID
        result = self._find_event_by_uuid(event_id)
        if result is None:
            return False
        
        roi_id, idx, _ = result
        events = self._velocity_events[roi_id]
        
        # Remove the event from the list
        events.pop(idx)
        self._velocity_events[roi_id] = events
        
        # Clean up UUID mappings
        if event_id in self._velocity_event_uuid_map:
            del self._velocity_event_uuid_map[event_id]
        if (roi_id, idx) in self._velocity_event_uuid_reverse:
            del self._velocity_event_uuid_reverse[(roi_id, idx)]
        
        # Update UUID mappings for events after the deleted one (indices shifted)
        # Rebuild reverse mapping for this ROI to fix indices
        for new_idx in range(idx, len(events)):
            old_key = (roi_id, new_idx + 1)
            if old_key in self._velocity_event_uuid_reverse:
                uuid = self._velocity_event_uuid_reverse.pop(old_key)
                new_key = (roi_id, new_idx)
                self._velocity_event_uuid_reverse[new_key] = uuid
                self._velocity_event_uuid_map[uuid] = new_key
        
        # Mark dirty
        self._dirty = True
        return True

    def get_velocity_report(self, roi_id: int | None = None) -> list[VelocityReportRow]:
        """Return velocity report rows for roi_id (or all ROIs if None).

        Used by gui, we are rounding values to 3 decimal places

        Args:
            roi_id: Identifier of the ROI, or None for all ROIs.

        Returns:
            Stored list of velocity report rows (possibly empty).
        """
        if roi_id is None:
            roi_ids = sorted(self._velocity_events.keys())
        else:
            roi_ids = [roi_id]

        event_dicts: list[VelocityReportRow] = []
        path = str(self.acq_image.path) if self.acq_image.path is not None else None
        for rid in roi_ids:
            events = self.get_velocity_events(rid)
            if not events:
                continue
            for idx, event in enumerate(events):
                event_dict = event.to_dict(round_decimals=3)
                # Use UUID as event_id (stable, doesn't change when event is updated)
                event_id = self._velocity_event_uuid_reverse.get((rid, idx))
                if event_id is None:
                    # Fallback: generate UUID if not found (shouldn't happen)
                    event_id = str(uuid4())
                    self._velocity_event_uuid_map[event_id] = (rid, idx)
                    self._velocity_event_uuid_reverse[(rid, idx)] = event_id
                event_dict["event_id"] = event_id
                event_dict["roi_id"] = rid
                event_dict["path"] = path
                event_dicts.append(event_dict)
        return event_dicts

    def __str__(self) -> str:
        """String representation."""
        roi_ids = [roi.id for roi in self.acq_image.rois]
        analyzed = sorted(self._analysis_metadata.keys())
        return f"KymAnalysis(roi_ids={roi_ids}, analyzed={analyzed}, dirty={self._dirty})"