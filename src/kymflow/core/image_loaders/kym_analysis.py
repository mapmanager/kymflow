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
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, TypedDict
from uuid import uuid4

import numpy as np
import pandas as pd

from kymflow.core.analysis.kym_flow_radon import mp_analyze_flow
from kymflow.core.analysis.utils import _medianFilter, _removeOutliers_sd, _removeOutliers_analyzeflow
from kymflow.core.utils.logging import get_logger
from kymflow.core.image_loaders.radon_analysis import RoiAnalysisMetadata, RadonAnalysis
from kymflow.core.image_loaders.radon_report import RadonReport
from kymflow.core.image_loaders.roi import ROI
from kymflow.core.image_loaders.velocity_event_report import VELOCITY_EVENT_CSV_ROUND_DECIMALS

# DEPRECATED: Stall analysis is deprecated
# from kymflow.core.analysis.stall_analysis import StallAnalysis, StallAnalysisParams
from kymflow.core.analysis.velocity_events.velocity_events import (
    BaselineDropParams,
    NanGapParams,
    UserType,
    VelocityEvent,
    ZeroGapParams,
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

# Re-export for backward compatibility (RADON_JSON_VERSION used by tests)
from kymflow.core.image_loaders.radon_analysis import RADON_JSON_VERSION


class VelocityReportRow(TypedDict):
    """Velocity event report row for export. Includes channel (anticipatory)."""

    event_id: str
    roi_id: int
    channel: int
    path: Optional[str]
    file_name: Optional[str]
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
        self._analysis_children["RadonAnalysis"] = RadonAnalysis(acq_image)
        self._dirty: bool = False
        self._velocity_events: Dict[int, List[VelocityEvent]] = {}
        # Velocity events are computed on-demand from stored analysis values (e.g., velocity).
        #
        # NOTE: VelocityEvent._uuid is the single source of truth for event IDs.
        # We no longer maintain separate UUID → (roi_id, index) mappings.
        
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
        return self._dirty or (radon.is_dirty if radon else False) or self.acq_image.is_metadata_dirty

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

        events_path = self._get_events_json_path()
        events_data = {
            "version": "1.0",
            "velocity_events": {
                str(rid): [
                    {**ev.to_dict(), "channel": (radon.get_channel_for_roi(rid) if radon else None) or 1}
                    for ev in evs
                ]
                for rid, evs in self._velocity_events.items()
            },
        }
        with open(events_path, "w") as f:
            json.dump(events_data, f, indent=2, default=str)
        self._dirty = False
        return metadata_saved or radon_saved
    
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
            self._load_velocity_events_from_dict(data.get("velocity_events", {}))
            self._reconcile_velocity_events_to_rois()
            self._dirty = False
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
                object.__setattr__(self.acq_image, "_accepted", ev_data.get("accepted", True))
            self._load_velocity_events_from_dict(ev_data.get("velocity_events", {}))
        self._reconcile_velocity_events_to_rois()
        self._dirty = False
        return True

    def _load_velocity_events_from_dict(self, events_dict: dict) -> None:
        self._velocity_events.clear()
        for roi_id_str, events_list in events_dict.items():
            try:
                roi_id = int(roi_id_str)
                events = [VelocityEvent.from_dict(ev) for ev in events_list]
                for e in events:
                    object.__setattr__(e, "_uuid", str(uuid4()))
                self._velocity_events[roi_id] = events
            except Exception:
                pass

    def _reconcile_velocity_events_to_rois(self) -> None:
        current = {roi.id for roi in self.acq_image.rois}
        for rid in list(self._velocity_events.keys()):
            if rid not in current:
                del self._velocity_events[rid]
        self._velocity_events = {rid: evs for rid, evs in self._velocity_events.items() if rid in current}

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
        radon = self.get_analysis_object("RadonAnalysis")
        if radon is None:
            raise ValueError("RadonAnalysis not available.")
        channel = radon.get_channel_for_roi(roi_id)
        if channel is None:
            raise ValueError(
                f"Cannot run velocity event analysis: ROI {roi_id} has no radon analysis (channel from metadata)."
            )
        velocity = radon.get_analysis_value(
            roi_id=roi_id,
            channel=channel,
            key=velocity_key,
            remove_outliers=remove_outliers,
        )
        if velocity is None:
            raise ValueError(
                f"Cannot run velocity event analysis: ROI {roi_id} has no analysis values for key '{velocity_key}'."
            )

        # explicitly remove outlierss like old v0 flowanalysis
        # velocity = _removeOutliers_analyzeflow(velocity)
        
        time_s = radon.get_analysis_value(
            roi_id=roi_id,
            channel=channel,
            key="time",
        )
        if time_s is None:
            raise ValueError(
                f"Cannot run velocity event analysis: ROI {roi_id} has no 'time' values."
            )

        # Run detection
        events, _debug = detect_events(
            time_s,
            velocity,
            baseline_drop_params=baseline_drop_params,
            nan_gap_params=nan_gap_params,
            zero_gap_params=zero_gap_params,
        )
        
        # Store results, if we had previous roi_id velocity events -> THIS REPLACES ALL OF THEM
        #self._velocity_events[roi_id] = events
        
        # remove existing events (do not remove 'user added' or true_stall)
        _nBefore = self.num_velocity_events(roi_id)
        
        self.remove_velocity_event(roi_id, "auto_detected")
        
        _nAfter = self.num_velocity_events(roi_id)
        
        # logger.info(f"roi:{roi_id} _nBefore:{_nBefore} _nAfter:{_nAfter} removed:{_nBefore - _nAfter}")

        # append detected event
        if roi_id not in self._velocity_events:
            self._velocity_events[roi_id] = events
        else:
            self._velocity_events[roi_id] = self._velocity_events[roi_id] + events
            # sort event by t_start
            self._velocity_events[roi_id].sort(key=lambda e: e.t_start)
        
        # Assign UUIDs to all events in the list (including newly detected ones)
        events_list = self._velocity_events[roi_id]
        for event in events_list:
            # Ensure each event has a UUID
            if event._uuid is None:
                event_uuid = str(uuid4())
                object.__setattr__(event, "_uuid", event_uuid)
        
        # Mark dirty so callers know there are unsaved results.
        self._dirty = True
        # Return events_list (all events with UUIDs assigned), not just newly detected events
        return events_list

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
        if roi_id not in self._velocity_events:
            return

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

    def num_user_added_velocity_events(self) -> int:
        """Return the total number of velocity events with event_type == "User Added" across all ROIs.

        Returns:
            Total number of user-added velocity events across all ROIs.
        """
        count = 0
        for events in self._velocity_events.values():
            count += sum(1 for event in events if event.event_type == "User Added")
        return count

    def get_velocity_events(self, roi_id: int) -> Optional[list[VelocityEvent]]:
        """Return velocity event results for roi_id, or None if not present.

        Args:
            roi_id: Identifier of the ROI.

        Returns:
            Stored list of VelocityEvent instances, or None if velocity event analysis
            has not been run for this ROI (or results were not loaded).
        """
        events = self._velocity_events.get(roi_id)
        if events is None:
            return None
        
        # Invariant: every event in _velocity_events has a non-None _uuid
        return events

    def get_velocity_events_filtered(
        self, roi_id: int, event_filter: dict[str, bool]
    ) -> Optional[list[VelocityEvent]]:
        """Return filtered velocity event results for roi_id.

        Args:
            roi_id: Identifier of the ROI.
            event_filter: Dict mapping event_type (str) to bool (True = include, False = exclude).

        Returns:
            Filtered list of VelocityEvent instances, or None if velocity event analysis
            has not been run for this ROI (or results were not loaded).
        """
        events = self._velocity_events.get(roi_id)
        if events is None:
            return None
        
        # Filter events where event_filter.get(event.event_type, True) is True
        # Default to True if event_type not in filter (show by default)
        return [
            event for event in events
            if event_filter.get(event.event_type, True) is True
        ]

    # def _velocity_event_id(self, roi_id: int, event: VelocityEvent) -> str:
    #     """Generate a stable event_id for a velocity event.
        
    #     DEPRECATED: This method is kept for backward compatibility but is no longer
    #     used for event identification. Events now use UUID-based event_id.
    #     """
    #     i_end_value = event.i_end if event.i_end is not None else "None"
    #     return f"{roi_id}:{event.i_start}:{i_end_value}:{event.event_type}"

    def _find_event_by_uuid(self, event_id: str) -> tuple[int, int, VelocityEvent] | None:
        """Find event by UUID event_id.
        
        Returns:
            Tuple of (roi_id, index, event) if found, None otherwise.
        """
        for roi_id, events in self._velocity_events.items():
            for idx, event in enumerate(events):
                if event._uuid == event_id:
                    return (roi_id, idx, event)
        return None

    def find_event_by_uuid(self, event_id: str) -> tuple[int, int, VelocityEvent] | None:
        """Find event by UUID event_id (public API).
        
        Args:
            event_id: UUID string identifying the event.
        
        Returns:
            Tuple of (roi_id, index, event) if found, None otherwise.
        """
        return self._find_event_by_uuid(event_id)

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
            events[idx] = replace(event, user_type=new_user_type, _uuid=event._uuid)
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
                _uuid=event._uuid,
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
                _uuid=event._uuid,
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
            _uuid=event._uuid,
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
        The event is appended to the ROI's event list and sorted by t_start.

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
            event_type="User Added",  # Default event type
            i_start=i_start,
            t_start=t_start,
            i_end=i_end,
            t_end=t_end,
            duration_sec=duration_sec,
            user_type=UserType.UNREVIEWED,  # Default user type
        )
        # Assign UUID to frozen dataclass using object.__setattr__
        event_uuid = str(uuid4())
        object.__setattr__(new_event, "_uuid", event_uuid)
        
        # Append to the ROI's event list
        if roi_id not in self._velocity_events:
            self._velocity_events[roi_id] = []
        self._velocity_events[roi_id].append(new_event)
        
        # Sort events by t_start (same as run_velocity_event_analysis)
        self._velocity_events[roi_id].sort(key=lambda e: e.t_start)
        
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
        
        # Mark dirty
        self._dirty = True
        return True

    def get_velocity_report(self, roi_id: int | None = None, *, blinded: bool = False) -> list[VelocityReportRow]:
        """Return velocity report rows for roi_id (or all ROIs if None).

        Used by gui, we are rounding values to 3 decimal places

        Args:
            roi_id: Identifier of the ROI, or None for all ROIs.
            blinded: If True, replace file names with "Blinded" and grandparent folder with "Blinded".

        Returns:
            Stored list of velocity report rows (possibly empty).
        """
        if roi_id is None:
            roi_ids = sorted(self._velocity_events.keys())
        else:
            roi_ids = [roi_id]

        event_dicts: list[VelocityReportRow] = []
        path = str(self.acq_image.path) if self.acq_image.path is not None else None
        
        _rowDict = self.acq_image.getRowDict(blinded=blinded)
        grandparent_folder = _rowDict.get("Grandparent Folder")
        if grandparent_folder is None:
            logger.warning('grandparent_folder is none -> happend when loaded with synth data in pytest')
            grandparent_folder = ""

        for rid in roi_ids:
            events = self.get_velocity_events(rid)
            if not events:
                continue
            for idx, event in enumerate(events):
                event_dict = event.to_dict(round_decimals=VELOCITY_EVENT_CSV_ROUND_DECIMALS)
                # Use event._uuid as event_id (stable, doesn't change when event is updated)
                if event._uuid is None:
                    # Defensive: assign a UUID if somehow missing
                    event_uuid = str(uuid4())
                    object.__setattr__(event, "_uuid", event_uuid)
                event_id = event._uuid
                # 20260217_fix_t_peak: guard for missing t_peak
                # if event.t_peak is None or (isinstance(event.t_peak, float) and not np.isfinite(event.t_peak)):
                #     logger.warning(
                #         "20260217_fix_t_peak: t_peak is missing/None for t_start:%s event_id=%s",
                #         event.t_start,
                #         event_id,
                #     )
                radon = self.get_analysis_object("RadonAnalysis")
                channel = (radon.get_channel_for_roi(rid) if radon else None) or 1
                event_dict["event_id"] = event_id
                event_dict["roi_id"] = rid
                event_dict["channel"] = channel
                event_dict["path"] = path
                if blinded:
                    event_dict["file_name"] = "Blinded"
                else:
                    event_dict["file_name"] = Path(path).stem if path else None
                event_dict["grandparent_folder"] = grandparent_folder
                event_dicts.append(event_dict)
        return event_dicts

    def get_velocity_event_row(self, event_id: str, *, blinded: bool = False) -> VelocityReportRow | None:
        """Return a single velocity report row for the given event_id.
        
        Args:
            event_id: UUID of the velocity event.
            blinded: If True, replace file names with "Blinded" and grandparent folder with "Blinded".
        
        Returns:
            Velocity report row dict, or None if event not found.
        """
        # Find the event by UUID
        result = self._find_event_by_uuid(event_id)
        if result is None:
            return None
        roi_id, idx, event = result
        events = self.get_velocity_events(roi_id)
        if not events or idx >= len(events):
            return None
        
        event = events[idx]
        event_dict = event.to_dict(round_decimals=VELOCITY_EVENT_CSV_ROUND_DECIMALS)
        
        # Ensure event object has _uuid matching the mapping
        if not hasattr(event, '_uuid') or event._uuid != event_id:
            object.__setattr__(event, '_uuid', event_id)
        
        path = str(self.acq_image.path) if self.acq_image.path is not None else None
        _rowDict = self.acq_image.getRowDict(blinded=blinded)
        grandparent_folder = _rowDict.get("Grandparent Folder")
        if grandparent_folder is None:
            grandparent_folder = ""
        
        radon = self.get_analysis_object("RadonAnalysis")
        channel = (radon.get_channel_for_roi(roi_id) if radon else None) or 1
        event_dict["event_id"] = event_id
        event_dict["roi_id"] = roi_id
        event_dict["channel"] = channel
        event_dict["path"] = path
        if blinded:
            event_dict["file_name"] = "Blinded"
        else:
            event_dict["file_name"] = Path(path).stem if path else None
        event_dict["grandparent_folder"] = grandparent_folder

        return event_dict

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
