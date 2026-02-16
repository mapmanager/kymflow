"""Velocity event report data structure for kym_event_db.csv.

This module provides the VelocityEventReport dataclass for representing
a single velocity event row in the kym event database. Mirrors RadonReport
pattern: identity + event fields, with to_dict/from_dict for CSV I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from kymflow.core.analysis.velocity_events.velocity_events import VelocityEvent


@dataclass(frozen=True)
class VelocityEventReport:
    """Immutable dataclass representing a single velocity event row for kym_event_db.csv.

    Combines identity (path, roi, rel_path) with all VelocityEvent attributes.
    Used when building/loading the velocity event database cache.
    """

    # Identity
    _unique_row_id: str
    path: Optional[str] = None
    roi_id: int = 0
    rel_path: Optional[str] = None

    # Folder metadata (from path structure, for grouping in plot pool)
    parent_folder: Optional[str] = None
    grandparent_folder: Optional[str] = None

    # VelocityEvent fields
    event_type: Optional[str] = None
    i_start: Optional[int] = None
    i_peak: Optional[int] = None
    i_end: Optional[int] = None
    t_start: Optional[float] = None
    t_peak: Optional[float] = None
    t_end: Optional[float] = None
    score_peak: Optional[float] = None
    baseline_before: Optional[float] = None
    baseline_after: Optional[float] = None
    strength: Optional[float] = None
    nan_fraction_in_event: Optional[float] = None
    n_valid_in_event: Optional[int] = None
    duration_sec: Optional[float] = None
    machine_type: Optional[str] = None
    user_type: Optional[str] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dictionary for CSV export."""
        return asdict(self)

    @classmethod
    def from_velocity_event(
        cls,
        event: "VelocityEvent",
        path_str: str,
        roi_id: int,
        event_idx: int,
        rel_path: Optional[str] = None,
        parent_folder: Optional[str] = None,
        grandparent_folder: Optional[str] = None,
        round_decimals: int = 3,
    ) -> "VelocityEventReport":
        """Build a VelocityEventReport from a VelocityEvent and DB metadata."""
        _unique_row_id = f"{path_str}|{roi_id}|{event_idx}"
        d = event.to_dict(round_decimals=round_decimals)
        return cls(
            _unique_row_id=_unique_row_id,
            path=path_str,
            roi_id=roi_id,
            rel_path=rel_path,
            parent_folder=parent_folder,
            grandparent_folder=grandparent_folder,
            event_type=d.get("event_type"),
            i_start=d.get("i_start"),
            i_peak=d.get("i_peak"),
            i_end=d.get("i_end"),
            t_start=d.get("t_start"),
            t_peak=d.get("t_peak"),
            t_end=d.get("t_end"),
            score_peak=d.get("score_peak"),
            baseline_before=d.get("baseline_before"),
            baseline_after=d.get("baseline_after"),
            strength=d.get("strength"),
            nan_fraction_in_event=d.get("nan_fraction_in_event"),
            n_valid_in_event=d.get("n_valid_in_event"),
            duration_sec=d.get("duration_sec"),
            machine_type=d.get("machine_type"),
            user_type=d.get("user_type"),
            note=d.get("note"),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VelocityEventReport":
        """Deserialize from a dictionary (e.g. loaded from CSV).

        Unknown keys are ignored. Missing keys use default values.
        """
        known_field_names = {f.name for f in fields(cls)}

        def _is_none_or_nan(v: Any) -> bool:
            if v is None:
                return True
            if isinstance(v, float) and v != v:
                return True
            return False

        filtered_data: Dict[str, Any] = {}
        for key in known_field_names:
            if key in data:
                value = data[key]
                if _is_none_or_nan(value):
                    value = None
                if key == "roi_id":
                    filtered_data[key] = int(value) if value is not None else 0
                elif key in ["i_start", "i_peak", "i_end", "n_valid_in_event"]:
                    filtered_data[key] = int(value) if value is not None else None
                elif key in [
                    "t_start", "t_peak", "t_end", "score_peak",
                    "baseline_before", "baseline_after", "strength",
                    "nan_fraction_in_event", "duration_sec",
                ]:
                    filtered_data[key] = float(value) if value is not None else None
                else:
                    filtered_data[key] = str(value) if value is not None else None

        if "_unique_row_id" not in filtered_data:
            filtered_data["_unique_row_id"] = ""

        return cls(**filtered_data)
