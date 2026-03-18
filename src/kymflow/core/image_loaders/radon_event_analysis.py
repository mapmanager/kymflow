"""Radon-based velocity event analysis for kymograph ROIs.

This module provides RadonEventAnalysis for velocity event detection and CRUD,
keyed by (roi_id, channel). All analysis is performed on (roi_id, channel).
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from uuid import uuid4

from kymflow.core.analysis.velocity_events.velocity_events import (
    BaselineDropParams,
    NanGapParams,
    UserType,
    VelocityEvent,
    ZeroGapParams,
    detect_events,
    time_to_index,
)
from kymflow.core.utils.logging import get_logger

from kymflow.core.image_loaders.acq_analysis_base import AcqAnalysisBase
from kymflow.core.image_loaders.velocity_event_report import (
    VELOCITY_EVENT_CSV_ROUND_DECIMALS,
)

if TYPE_CHECKING:
    from kymflow.core.image_loaders.acq_image import AcqImage
    from kymflow.core.image_loaders.radon_analysis import RadonAnalysis
    from kymflow.core.image_loaders.velocity_event_report import VelocityReportRow

logger = get_logger(__name__)

EVENTS_JSON_VERSION = "2.0"


def _meta_key(roi_id: int, channel: int) -> Tuple[int, int]:
    """Return canonical key for (roi_id, channel)."""
    return (roi_id, channel)


class RadonEventAnalysis(AcqAnalysisBase):
    """Velocity event analysis keyed by (roi_id, channel).

    All analysis, save, load, and get/set operations use (roi_id, channel) explicitly.
    Depends on RadonAnalysis for velocity/time data.
    """

    analysis_name: str = "RadonEventAnalysis"

    def __init__(
        self,
        acq_image: "AcqImage",
        radon_analysis: "RadonAnalysis",
    ) -> None:
        """Initialize RadonEventAnalysis.

        Args:
            acq_image: Parent AcqImage instance.
            radon_analysis: Injected RadonAnalysis instance for velocity/time lookups.
        """
        super().__init__(acq_image)
        self._radon: RadonAnalysis = radon_analysis
        self._velocity_events: Dict[Tuple[int, int], List[VelocityEvent]] = {}
        self._dirty: bool = False

    def iter_roi_channel_keys(self) -> List[Tuple[int, int]]:
        """Return all (roi_id, channel) keys that have velocity events."""
        return list(self._velocity_events.keys())

    @property
    def is_dirty(self) -> bool:
        """Return True if this analysis has unsaved changes."""
        return self._dirty

    def _get_primary_path(self) -> Optional[Path]:
        """Return primary file path for this image."""
        return self.acq_image.path

    def _get_events_json_path(self, folder_path: Path) -> Path:
        """Return path for *_events.json in the given folder."""
        primary_path = self._get_primary_path()
        if primary_path is None:
            raise ValueError("No file path available for events JSON")
        return folder_path / f"{primary_path.stem}_events.json"

    def save_analysis(self, folder_path: Path) -> bool:
        """Save velocity events to *_events.json.

        Format: {"version": "2.0", "velocity_events": {"roi_id:channel": [event_dicts]}}.

        Args:
            folder_path: Analysis folder path.

        Returns:
            True if saved.
        """
        if not self._dirty:
            return False
        path = self._get_events_json_path(folder_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        events_data: Dict[str, Any] = {
            "version": EVENTS_JSON_VERSION,
            "velocity_events": {},
        }
        for (rid, ch), evs in self._velocity_events.items():
            key = f"{rid}:{ch}"
            events_data["velocity_events"][key] = [
                {**ev.to_dict(), "channel": ch} for ev in evs
            ]
        with open(path, "w") as f:
            json.dump(events_data, f, indent=2, default=str)
        self._dirty = False
        return True

    def load_analysis(self, folder_path: Path) -> bool:
        """Load velocity events from *_events.json or legacy format.

        Supports v2.0 format (roi_id:channel keys) and legacy v1.0 (roi_id keys).

        Args:
            folder_path: Analysis folder path.

        Returns:
            True if loaded.
        """
        path = self._get_events_json_path(folder_path)
        if not path.exists():
            return False
        with open(path, "r") as f:
            ev_data = json.load(f)
        version = str(ev_data.get("version", "1.0"))
        raw = ev_data.get("velocity_events", {})
        self._load_velocity_events_from_dict(raw, version=version)
        self._reconcile_velocity_events_to_rois()
        self._dirty = False
        return True

    def _load_velocity_events_from_dict(
        self, events_dict: Dict[str, Any], version: str = "1.0"
    ) -> None:
        """Load velocity events from serialized dict.

        Args:
            events_dict: Dict mapping "roi_id" or "roi_id:channel" to list of event dicts.
            version: "1.0" = roi_id keys, channel in each event; "2.0" = roi_id:channel keys.
        """
        self._velocity_events.clear()
        for key_str, events_list in events_dict.items():
            try:
                if version.startswith("2."):
                    parts = key_str.split(":")
                    if len(parts) != 2:
                        continue
                    roi_id, channel = int(parts[0]), int(parts[1])
                else:
                    roi_id = int(key_str)
                    channel = 1
                    if events_list and isinstance(events_list[0], dict):
                        ch = events_list[0].get("channel")
                        if ch is not None:
                            channel = int(ch)
                events = [VelocityEvent.from_dict(ev) for ev in events_list]
                for e in events:
                    object.__setattr__(e, "_uuid", str(uuid4()))
                self._velocity_events[_meta_key(roi_id, channel)] = events
            except Exception:
                pass

    def _reconcile_velocity_events_to_rois(self) -> None:
        """Remove events for ROIs that no longer exist."""
        current = {roi.id for roi in self.acq_image.rois}
        to_remove = [
            (rid, ch)
            for (rid, ch) in self._velocity_events
            if rid not in current
        ]
        for k in to_remove:
            del self._velocity_events[k]

    def get_all_roi_channel_pairs(self) -> List[Tuple[int, int]]:
        """Return all (roi_id, channel) pairs with events.

        Returns:
            List of (roi_id, channel) tuples.
        """
        return list(self._velocity_events.keys())

    def run_velocity_event_analysis(
        self,
        roi_id: int,
        channel: int,
        *,
        velocity_key: str = "velocity",
        remove_outliers: bool = False,
        baseline_drop_params: Optional[BaselineDropParams] = None,
        nan_gap_params: Optional[NanGapParams] = None,
        zero_gap_params: Optional[ZeroGapParams] = None,
    ) -> List[VelocityEvent]:
        """Run velocity event detection for (roi_id, channel) and store results.

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.
            velocity_key: Column name for velocity (e.g. "velocity", "cleanVelocity").
            remove_outliers: If True, remove outliers before detection.
            baseline_drop_params: Optional params for baseline-drop detection.
            nan_gap_params: Optional params for NaN-gap detection.
            zero_gap_params: Optional params for zero-gap detection.

        Returns:
            List of detected VelocityEvent instances.

        Raises:
            ValueError: If analysis values are missing for (roi_id, channel).
        """
        velocity = self._radon.get_analysis_value(
            roi_id=roi_id,
            channel=channel,
            key=velocity_key,
            remove_outliers=remove_outliers,
        )
        if velocity is None:
            raise ValueError(
                f"Cannot run velocity event analysis: (roi_id={roi_id}, channel={channel}) "
                f"has no analysis values for key '{velocity_key}'."
            )
        time_s = self._radon.get_analysis_value(
            roi_id=roi_id, channel=channel, key="time"
        )
        if time_s is None:
            raise ValueError(
                f"Cannot run velocity event analysis: (roi_id={roi_id}, channel={channel}) "
                "has no 'time' values."
            )
        events, _ = detect_events(
            time_s,
            velocity,
            baseline_drop_params=baseline_drop_params or BaselineDropParams(),
            nan_gap_params=nan_gap_params or NanGapParams(),
            zero_gap_params=zero_gap_params or ZeroGapParams(),
        )
        key = _meta_key(roi_id, channel)
        self.remove_velocity_event(roi_id, channel, "auto_detected")
        if key not in self._velocity_events:
            self._velocity_events[key] = list(events)
        else:
            self._velocity_events[key] = self._velocity_events[key] + list(events)
            self._velocity_events[key].sort(key=lambda e: e.t_start)
        events_list = self._velocity_events[key]
        for event in events_list:
            if event._uuid is None:
                object.__setattr__(event, "_uuid", str(uuid4()))
        self._dirty = True
        return events_list

    def remove_velocity_event(
        self, roi_id: int, channel: int, remove_these: str
    ) -> None:
        """Remove velocity events by type for (roi_id, channel).

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.
            remove_these: "_remove_all" or "auto_detected".

        Raises:
            ValueError: If remove_these is invalid.
        """
        key = _meta_key(roi_id, channel)
        if key not in self._velocity_events:
            return
        if remove_these == "_remove_all":
            self._velocity_events[key] = []
        elif remove_these == "auto_detected":
            self._velocity_events[key] = [
                e
                for e in self._velocity_events[key]
                if e.event_type == "User Added" or e.user_type != "unreviewed"
            ]
        else:
            raise ValueError(f"Invalid remove_these value: {remove_these}")
        self._dirty = True

    def num_velocity_events(self, roi_id: int, channel: int) -> int:
        """Return number of velocity events for (roi_id, channel)."""
        return len(self._velocity_events.get(_meta_key(roi_id, channel), []))

    def total_num_velocity_events(self) -> int:
        """Return total velocity events across all (roi_id, channel)."""
        return sum(len(evs) for evs in self._velocity_events.values())

    def num_user_added_velocity_events(self) -> int:
        """Return count of user-added velocity events."""
        count = 0
        for events in self._velocity_events.values():
            count += sum(1 for e in events if e.event_type == "User Added")
        return count

    def get_velocity_events(
        self, roi_id: int, channel: int
    ) -> Optional[List[VelocityEvent]]:
        """Return velocity events for (roi_id, channel), or None."""
        return self._velocity_events.get(_meta_key(roi_id, channel))

    def get_velocity_events_filtered(
        self, roi_id: int, channel: int, event_filter: Dict[str, bool]
    ) -> Optional[List[VelocityEvent]]:
        """Return velocity events filtered by event_type for (roi_id, channel).

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.
            event_filter: Dict mapping event_type to bool; True = include.

        Returns:
            Filtered list of events, or None if no events for (roi_id, channel).
        """
        events = self._velocity_events.get(_meta_key(roi_id, channel))
        if events is None:
            return None
        return [
            e for e in events
            if event_filter.get(e.event_type, True) is True
        ]

    def _find_event_by_uuid(
        self, event_id: str
    ) -> Optional[Tuple[int, int, int, VelocityEvent]]:
        """Find event by UUID. Returns (roi_id, channel, index, event) or None."""
        for (rid, ch), events in self._velocity_events.items():
            for idx, event in enumerate(events):
                if event._uuid == event_id:
                    return (rid, ch, idx, event)
        return None

    def find_event_by_uuid(
        self, event_id: str
    ) -> Optional[Tuple[int, int, int, VelocityEvent]]:
        """Find event by UUID. Returns (roi_id, channel, index, event) or None."""
        return self._find_event_by_uuid(event_id)

    def update_velocity_event_field(
        self, event_id: str, field: str, value: Any
    ) -> Optional[str]:
        """Update a field on a velocity event by event_id.

        Args:
            event_id: UUID of the event to update.
            field: Field name; one of "user_type", "t_start", "t_end".
            value: New value for the field.

        Returns:
            The event_id if update succeeded, None otherwise.
        """
        if field not in {"user_type", "t_start", "t_end"}:
            logger.warning('Unsupported velocity event update field: "%s"', field)
            return None
        new_user_type: Optional[UserType] = None
        new_t_start: Optional[float] = None
        new_t_end: Optional[float] = None
        if field == "user_type":
            try:
                new_user_type = UserType(str(value))
            except Exception:
                return None
        elif field == "t_start":
            try:
                new_t_start = float(value)
            except Exception:
                return None
        elif field == "t_end":
            new_t_end = float(value) if value is not None else None
        result = self._find_event_by_uuid(event_id)
        if result is None:
            return None
        roi_id, channel, idx, event = result
        key = _meta_key(roi_id, channel)
        events = self._velocity_events[key]
        seconds_per_line = float(self.acq_image.seconds_per_line)
        if field == "user_type":
            events[idx] = replace(event, user_type=new_user_type, _uuid=event._uuid)
        elif field == "t_start" and new_t_start is not None:
            new_dur = (
                float(event.t_end) - new_t_start
                if event.t_end is not None
                else None
            )
            events[idx] = replace(
                event,
                t_start=new_t_start,
                i_start=time_to_index(new_t_start, seconds_per_line),
                duration_sec=new_dur,
                _uuid=event._uuid,
            )
        elif field == "t_end":
            new_i_end = (
                time_to_index(new_t_end, seconds_per_line)
                if new_t_end is not None
                else None
            )
            new_dur = (
                float(new_t_end) - float(event.t_start)
                if new_t_end is not None
                else None
            )
            events[idx] = replace(
                event,
                t_end=new_t_end,
                i_end=new_i_end,
                duration_sec=new_dur,
                _uuid=event._uuid,
            )
        self._velocity_events[key] = events
        self._dirty = True
        return event_id

    def update_velocity_event_range(
        self, event_id: str, t_start: float, t_end: Optional[float]
    ) -> Optional[str]:
        """Update t_start and t_end atomically for an event.

        Args:
            event_id: UUID of the event to update.
            t_start: New start time (seconds).
            t_end: New end time (seconds), or None.

        Returns:
            The event_id if update succeeded, None otherwise.
        """
        try:
            new_t_start = float(t_start)
            new_t_end = float(t_end) if t_end is not None else None
        except (ValueError, TypeError):
            return None
        result = self._find_event_by_uuid(event_id)
        if result is None:
            return None
        roi_id, channel, idx, event = result
        key = _meta_key(roi_id, channel)
        seconds_per_line = float(self.acq_image.seconds_per_line)
        events = self._velocity_events[key]
        events[idx] = replace(
            event,
            t_start=new_t_start,
            i_start=time_to_index(new_t_start, seconds_per_line),
            t_end=new_t_end,
            i_end=(
                time_to_index(new_t_end, seconds_per_line)
                if new_t_end is not None
                else None
            ),
            duration_sec=(
                float(new_t_end) - new_t_start if new_t_end is not None else None
            ),
            _uuid=event._uuid,
        )
        self._velocity_events[key] = events
        self._dirty = True
        return event_id

    def add_velocity_event(
        self,
        roi_id: int,
        channel: int,
        t_start: float,
        t_end: Optional[float] = None,
    ) -> str:
        """Add a new velocity event for (roi_id, channel).

        Returns:
            UUID of the new event.
        """
        roi = self.acq_image.rois.get(roi_id)
        if roi is None:
            raise ValueError(f"ROI {roi_id} not found")
        seconds_per_line = float(self.acq_image.seconds_per_line)
        i_start = time_to_index(t_start, seconds_per_line)
        i_end = (
            time_to_index(t_end, seconds_per_line)
            if t_end is not None
            else None
        )
        duration_sec = (
            float(t_end - t_start) if t_end is not None else None
        )
        new_event = VelocityEvent(
            event_type="User Added",
            i_start=i_start,
            t_start=t_start,
            i_end=i_end,
            t_end=t_end,
            duration_sec=duration_sec,
            user_type=UserType.UNREVIEWED,
        )
        event_uuid = str(uuid4())
        object.__setattr__(new_event, "_uuid", event_uuid)
        key = _meta_key(roi_id, channel)
        if key not in self._velocity_events:
            self._velocity_events[key] = []
        self._velocity_events[key].append(new_event)
        self._velocity_events[key].sort(key=lambda e: e.t_start)
        self._dirty = True
        return event_uuid

    def delete_velocity_event(self, event_id: str) -> bool:
        """Delete velocity event by UUID. Returns True if deleted."""
        result = self._find_event_by_uuid(event_id)
        if result is None:
            return False
        roi_id, channel, idx, _ = result
        key = _meta_key(roi_id, channel)
        events = self._velocity_events[key]
        events.pop(idx)
        self._velocity_events[key] = events
        self._dirty = True
        return True

    def get_velocity_report(
        self,
        roi_id: Optional[int] = None,
        channel: Optional[int] = None,
        *,
        blinded: bool = False,
    ) -> List["VelocityReportRow"]:
        """Return velocity report rows.

        When roi_id and channel are both None, returns all events.
        Otherwise both must be provided.
        """
        from kymflow.core.image_loaders.velocity_event_report import VelocityReportRow

        path = str(self.acq_image.path) if self.acq_image.path else None
        row_dict = self.acq_image.getRowDict(blinded=blinded)
        grandparent_folder = row_dict.get("Grandparent Folder") or ""
        event_dicts: List[VelocityReportRow] = []
        if roi_id is None and channel is None:
            keys = list(self._velocity_events.keys())
        else:
            if roi_id is None or channel is None:
                return []
            keys = [_meta_key(roi_id, channel)]
            if keys[0] not in self._velocity_events:
                return []
        for (rid, ch) in keys:
            events = self._velocity_events.get((rid, ch))
            if not events:
                continue
            for idx, event in enumerate(events):
                d = event.to_dict(round_decimals=VELOCITY_EVENT_CSV_ROUND_DECIMALS)
                if event._uuid is None:
                    object.__setattr__(event, "_uuid", str(uuid4()))
                d["event_id"] = event._uuid
                d["roi_id"] = rid
                d["channel"] = ch
                d["path"] = path
                d["file_name"] = (Path(path).stem if path else None) if not blinded else "Blinded"
                d["grandparent_folder"] = grandparent_folder
                event_dicts.append(d)
        return event_dicts

    def get_velocity_event_row(
        self, event_id: str, *, blinded: bool = False
    ) -> Optional["VelocityReportRow"]:
        """Return a single velocity report row by event_id.

        Args:
            event_id: UUID of the event.
            blinded: If True, blind file_name and grandparent_folder.

        Returns:
            Report row dict, or None if event not found.
        """
        from kymflow.core.image_loaders.velocity_event_report import VelocityReportRow

        result = self._find_event_by_uuid(event_id)
        if result is None:
            return None
        roi_id, channel, idx, event = result
        events = self.get_velocity_events(roi_id, channel)
        if not events or idx >= len(events):
            return None
        event = events[idx]
        d = event.to_dict(round_decimals=VELOCITY_EVENT_CSV_ROUND_DECIMALS)
        path = str(self.acq_image.path) if self.acq_image.path else None
        row_dict = self.acq_image.getRowDict(blinded=blinded)
        grandparent_folder = row_dict.get("Grandparent Folder") or ""
        d["event_id"] = event_id
        d["roi_id"] = roi_id
        d["channel"] = channel
        d["path"] = path
        d["file_name"] = "Blinded" if blinded else (Path(path).stem if path else None)
        d["grandparent_folder"] = grandparent_folder
        return d
