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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional
import numpy as np
import pandas as pd

from kymflow.core.analysis.kym_flow_radon import mp_analyze_flow
from kymflow.core.analysis.utils import _medianFilter, _removeOutliers_sd, _removeOutliers_analyzeflow
from kymflow.core.utils.logging import get_logger
from kymflow.core.image_loaders.radon_analysis import RoiAnalysisMetadata, RadonAnalysis
from kymflow.core.image_loaders.radon_event_analysis import RadonEventAnalysis
from kymflow.core.image_loaders.radon_report import RadonReport
from kymflow.core.image_loaders.roi import ROI
from kymflow.core.image_loaders.velocity_event_report import VelocityReportRow

# DEPRECATED: Stall analysis is deprecated
# from kymflow.core.analysis.stall_analysis import StallAnalysis, StallAnalysisParams
from kymflow.core.analysis.velocity_events.velocity_events import (
    BaselineDropParams,
    NanGapParams,
    UserType,
    VelocityEvent,
    ZeroGapParams,
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

# Re-export for backward compatibility (RADON_JSON_VERSION used by tests)
from kymflow.core.image_loaders.radon_analysis import RADON_JSON_VERSION


class KymAnalysis:
    """Manages ROIs and performs flow analysis on kymograph images.
    
    KymAnalysis provides a unified API for managing ROIs and their associated
    analysis results. ROI geometry lives in AcqImage.rois; KymAnalysis stores
    only analysis state/results metadata. When ROI coordinates change, analysis
    becomes invalid and must be re-run.
    
    Attributes:
        acq_image: Reference to the parent AcqImage (typically KymImage).
        _analysis_metadata: Dict mapping (roi_id, channel) to RoiAnalysisMetadata.
        _df: DataFrame containing all analysis results with roi_id and channel columns.
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
        self._analysis_children: Dict[str, Any] = {}
        radon = RadonAnalysis(acq_image)
        self._analysis_children["RadonAnalysis"] = radon
        self._analysis_children["RadonEventAnalysis"] = RadonEventAnalysis(
            acq_image, radon
        )
        self._dirty: bool = False

        # Always try to load analysis (handles path=None gracefully)
        self.load_analysis()

    def get_analysis_object(self, name: str):
        """Return the analysis object by name, or None.

        Args:
            name: Analysis name (e.g. "RadonAnalysis").

        Returns:
            The analysis instance, or None if not found.
        """
        return self._analysis_children.get(name)

    @property
    def num_rois(self) -> int:
        """Number of ROIs on the parent image (single source of truth)."""
        return self.acq_image.rois.numRois()

    @property
    def is_dirty(self) -> bool:
        """Return True if analysis or metadata/ROI changes are unsaved."""
        radon = self.get_analysis_object("RadonAnalysis")
        rea = self.get_analysis_object("RadonEventAnalysis")
        return (
            self._dirty
            or (radon.is_dirty if radon else False)
            or (rea.is_dirty if rea else False)
            or self.acq_image.is_metadata_dirty
        )

    def get_accepted(self) -> bool:
        """Return the accepted status (delegates to AcqImage)."""
        return self.acq_image.get_accepted()

    def set_accepted(self, value: bool) -> None:
        """Set the accepted status (delegates to AcqImage, marks dirty)."""
        self.acq_image.set_accepted(value)
        self._dirty = True

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
    
    def get_radon_save_paths(self) -> tuple[Path, Path] | None:
        """Get (csv_path, json_path) for RadonAnalysis files. Returns None if no path available."""
        try:
            folder = self._get_analysis_folder_path()
        except ValueError:
            return None
        radon = self.get_analysis_object("RadonAnalysis")
        return radon._get_radon_paths(folder) if radon else None

    def _get_events_json_path(self) -> Path:
        """Get the path for velocity events JSON (*_events.json)."""
        analysis_folder = self._get_analysis_folder_path()
        primary_path = self._get_primary_path()
        if primary_path is None:
            raise ValueError("No file path available for events JSON path")
        return analysis_folder / f"{primary_path.stem}_events.json"

    def _get_legacy_combined_paths(self) -> tuple[Path, Path]:
        """Legacy combined CSV and JSON paths (for v2.0 migration)."""
        analysis_folder = self._get_analysis_folder_path()
        primary_path = self._get_primary_path()
        if primary_path is None:
            raise ValueError("No file path available")
        base = primary_path.stem
        return analysis_folder / f"{base}_kymanalysis.csv", analysis_folder / f"{base}_kymanalysis.json"

    def save_analysis(self) -> bool:
        """Save analysis results. Delegates to RadonAnalysis and saves velocity events to *_events.json."""
        primary_path = self._get_primary_path()
        if primary_path is None:
            logger.warning("No path provided, analysis cannot be saved")
            return False
        if not self.is_dirty:
            logger.info(f"Analysis does not need to be saved for {primary_path.name}")
            return False

        metadata_saved = self.acq_image.save_metadata()
        if not metadata_saved:
            logger.warning("Failed to save metadata (ROIs), but continuing with analysis save")

        analysis_folder = self._get_analysis_folder_path()
        analysis_folder.mkdir(parents=True, exist_ok=True)
        radon = self.get_analysis_object("RadonAnalysis")
        radon_saved = radon.save_analysis(analysis_folder) if radon else False
        rea = self.get_analysis_object("RadonEventAnalysis")
        rea_saved = rea.save_analysis(analysis_folder) if rea else False
        ok = metadata_saved or radon_saved or rea_saved
        if ok:
            self._dirty = False
        return ok
    
    def load_analysis(self) -> bool:
        """Load analysis. RadonAnalysis loads its own files; v2.0 migration for legacy combined JSON."""
        primary_path = self._get_primary_path()
        if primary_path is None:
            return False
        try:
            analysis_folder = self._get_analysis_folder_path()
        except ValueError:
            return False
        radon_json = analysis_folder / f"{primary_path.stem}_radon.json"
        legacy_csv, legacy_json = self._get_legacy_combined_paths()

        if radon_json.exists():
            radon = self.get_analysis_object("RadonAnalysis")
            if radon:
                radon.load_analysis(analysis_folder)
        elif legacy_json.exists():
            with open(legacy_json, "r") as f:
                data = json.load(f)
            v = str(data.get("version", ""))
            if "analysis_metadata" not in data or not (v.startswith("2.") or v.startswith("3.")):
                return False
            radon = self.get_analysis_object("RadonAnalysis")
            if radon:
                radon.load_from_combined_v2(data, legacy_csv)
            if "accepted" in data:
                object.__setattr__(self.acq_image, "_accepted", data.get("accepted", True))
            rea = self.get_analysis_object("RadonEventAnalysis")
            if rea:
                rea._load_velocity_events_from_dict(
                    data.get("velocity_events", {}), version="1.0"
                )
                rea._reconcile_velocity_events_to_rois()
            return True
        else:
            radon = self.get_analysis_object("RadonAnalysis")
            if not radon or not radon.load_analysis(analysis_folder):
                return False

        events_path = self._get_events_json_path()
        if events_path.exists():
            with open(events_path, "r") as f:
                ev_data = json.load(f)
            if "accepted" in ev_data:
                object.__setattr__(
                    self.acq_image, "_accepted", ev_data.get("accepted", True)
                )
            rea = self.get_analysis_object("RadonEventAnalysis")
            if rea:
                version = str(ev_data.get("version", "1.0"))
                rea._load_velocity_events_from_dict(
                    ev_data.get("velocity_events", {}), version=version
                )
                rea._reconcile_velocity_events_to_rois()
        return True

    def get_time_bounds(self, roi_id: int) -> tuple[float, float] | None:
        """Get time range for ROI in physical units.
        
        Returns the time bounds (min, max) in seconds for the specified ROI,
        computed from ROI pixel bounds and voxel size. This method works
        without requiring analysis data - it calculates bounds directly from
        ROI coordinates and seconds_per_line.
        
        Args:
            roi_id: ROI identifier.
        
        Returns:
            Tuple of (time_min, time_max) in seconds, or None if:
            - ROI not found
            - Voxels not available
        """
        # Get ROI
        roi = self.acq_image.rois.get(roi_id)
        if roi is None:
            return None
        
        # Get voxels from header
        voxels = self.acq_image.header.voxels
        if voxels is None:
            return None
        
        # Call lower-level API on ROI
        return roi.get_time_bounds(voxels)

    def run_velocity_event_analysis(
        self,
        roi_id: int,
        channel: int,
        *,
        velocity_key: str = "velocity",
        remove_outliers: bool = False,
        baseline_drop_params: Optional["BaselineDropParams"] = None,
        nan_gap_params: Optional["NanGapParams"] = None,
        zero_gap_params: Optional["ZeroGapParams"] = None,
    ) -> list[VelocityEvent]:
        """Run velocity event detection for a single ROI and store results.

        This method is intentionally **on-demand**: it does not run automatically
        when flow analysis is computed. A caller (GUI/script) explicitly requests
        event detection once the underlying analysis values exist.

        The source signal is selected via `velocity_key` (e.g. 'velocity',
        'cleanVelocity', 'absVelocity').

        Args:
            roi_id: Identifier of the ROI to analyze.
            channel: 1-based channel index to analyze.
            velocity_key: Column name to retrieve from analysis (default: "velocity").
            remove_outliers: If True, remove outliers using 2*std threshold before detection.
            baseline_drop_params: Optional BaselineDropParams instance for baseline-drop detection.
                If None, uses default BaselineDropParams().
            nan_gap_params: Optional NanGapParams instance for NaN-gap detection.
                If None, uses default NanGapParams().
            zero_gap_params: Optional ZeroGapParams instance for zero-gap detection.
                If None, uses default ZeroGapParams().

        Returns:
            List of detected VelocityEvent instances.

        Raises:
            ValueError: If the requested analysis values are missing for this ROI.
        """
        rea = self.get_analysis_object("RadonEventAnalysis")
        if rea is None:
            raise ValueError("RadonEventAnalysis not available.")
        return rea.run_velocity_event_analysis(
            roi_id,
            channel,
            velocity_key=velocity_key,
            remove_outliers=remove_outliers,
            baseline_drop_params=baseline_drop_params,
            nan_gap_params=nan_gap_params,
            zero_gap_params=zero_gap_params,
        )

    def remove_velocity_event(
        self, roi_id: int, channel: int, remove_these: str
    ) -> None:
        """Remove velocity events by type for (roi_id, channel).

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.
            remove_these: "_remove_all" or "auto_detected".
        """
        rea = self.get_analysis_object("RadonEventAnalysis")
        if rea:
            rea.remove_velocity_event(roi_id, channel, remove_these)

    def num_velocity_events(self, roi_id: int, channel: int) -> int:
        """Return the number of velocity events for (roi_id, channel).

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.

        Returns:
            Count of velocity events.
        """
        rea = self.get_analysis_object("RadonEventAnalysis")
        return rea.num_velocity_events(roi_id, channel) if rea else 0


    def total_num_velocity_events(self) -> int:
        """Return the total number of velocity events across all (roi_id, channel)."""
        rea = self.get_analysis_object("RadonEventAnalysis")
        return rea.total_num_velocity_events() if rea else 0

    def num_user_added_velocity_events(self) -> int:
        """Return the total number of user-added velocity events."""
        rea = self.get_analysis_object("RadonEventAnalysis")
        return rea.num_user_added_velocity_events() if rea else 0

    def get_velocity_events(self, roi_id: int, channel: int) -> Optional[list[VelocityEvent]]:
        """Return velocity event results for (roi_id, channel), or None.

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.

        Returns:
            List of VelocityEvent, or None if no events for (roi_id, channel).
        """
        rea = self.get_analysis_object("RadonEventAnalysis")
        return rea.get_velocity_events(roi_id, channel) if rea else None

    def get_velocity_events_filtered(
        self, roi_id: int, channel: int, event_filter: dict[str, bool]
    ) -> Optional[list[VelocityEvent]]:
        """Return filtered velocity event results for (roi_id, channel).

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.
            event_filter: Dict mapping event_type to bool (True = include).

        Returns:
            Filtered list of VelocityEvent, or None if no events for (roi_id, channel).
        """
        rea = self.get_analysis_object("RadonEventAnalysis")
        return (
            rea.get_velocity_events_filtered(roi_id, channel, event_filter)
            if rea
            else None
        )

    # def _velocity_event_id(self, roi_id: int, event: VelocityEvent) -> str:
    #     """Generate a stable event_id for a velocity event.
        
    #     DEPRECATED: This method is kept for backward compatibility but is no longer
    #     used for event identification. Events now use UUID-based event_id.
    #     """
    #     i_end_value = event.i_end if event.i_end is not None else "None"
    #     return f"{roi_id}:{event.i_start}:{i_end_value}:{event.event_type}"

    def _find_event_by_uuid(
        self, event_id: str
    ) -> tuple[int, int, int, VelocityEvent] | None:
        """Find event by UUID. Returns (roi_id, channel, index, event) or None."""
        rea = self.get_analysis_object("RadonEventAnalysis")
        return rea._find_event_by_uuid(event_id) if rea else None

    def find_event_by_uuid(
        self, event_id: str
    ) -> tuple[int, int, int, VelocityEvent] | None:
        """Find event by UUID. Returns (roi_id, channel, index, event) or None."""
        return self._find_event_by_uuid(event_id)

    def update_velocity_event_field(
        self, event_id: str, field: str, value: Any
    ) -> str | None:
        """Update a field on a velocity event by event_id."""
        rea = self.get_analysis_object("RadonEventAnalysis")
        return rea.update_velocity_event_field(event_id, field, value) if rea else None

    def update_velocity_event_range(
        self, event_id: str, t_start: float, t_end: float | None
    ) -> str | None:
        """Update t_start and t_end atomically."""
        rea = self.get_analysis_object("RadonEventAnalysis")
        return (
            rea.update_velocity_event_range(event_id, t_start, t_end) if rea else None
        )

    def add_velocity_event(
        self, roi_id: int, channel: int, t_start: float, t_end: float | None = None
    ) -> str:
        """Add a new velocity event for (roi_id, channel).

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.
            t_start: Event start time in seconds.
            t_end: Event end time in seconds, or None.

        Returns:
            UUID of the new event.
        """
        rea = self.get_analysis_object("RadonEventAnalysis")
        if rea is None:
            raise ValueError("RadonEventAnalysis not available.")
        return rea.add_velocity_event(roi_id, channel, t_start, t_end)

    def delete_velocity_event(self, event_id: str) -> bool:
        """Delete a velocity event by UUID event_id."""
        rea = self.get_analysis_object("RadonEventAnalysis")
        return rea.delete_velocity_event(event_id) if rea else False

    def get_velocity_report(
        self,
        roi_id: int | None = None,
        channel: int | None = None,
        *,
        blinded: bool = False,
    ) -> list[VelocityReportRow]:
        """Return velocity report rows.

        Args:
            roi_id: ROI identifier, or None for all ROIs.
            channel: 1-based channel index, or None. When roi_id is given, channel must
                also be given. Pass both None for all (roi_id, channel) pairs.
            blinded: If True, blind file_name and grandparent_folder in output.

        Returns:
            List of VelocityReportRow dicts.
        """
        rea = self.get_analysis_object("RadonEventAnalysis")
        return (
            rea.get_velocity_report(roi_id, channel, blinded=blinded) if rea else []
        )

    def get_velocity_event_row(
        self, event_id: str, *, blinded: bool = False
    ) -> VelocityReportRow | None:
        """Return a single velocity report row by event_id."""
        rea = self.get_analysis_object("RadonEventAnalysis")
        return rea.get_velocity_event_row(event_id, blinded=blinded) if rea else None

    def get_radon_report(self) -> List[RadonReport]:
        """Delegate to RadonAnalysis. Prefer get_analysis_object('RadonAnalysis').get_radon_report(accepted=...)."""
        radon = self.get_analysis_object("RadonAnalysis")
        return radon.get_radon_report(accepted=self.get_accepted()) if radon else []

    def __str__(self) -> str:
        """String representation."""
        roi_ids = [roi.id for roi in self.acq_image.rois]
        radon = self.get_analysis_object("RadonAnalysis")
        analyzed = sorted(radon._analysis_metadata.keys()) if radon else []
        return f"KymAnalysis(roi_ids={roi_ids}, analyzed={analyzed}, dirty={self._dirty})"
