from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from math import ceil, floor
from typing import Optional, Literal, Any, Dict

# assumes these exist in your codebase
# from .enums import EventType, MachineType, UserType


RoundingMode = Literal["round", "floor", "ceil"]


def _time_to_index(t_sec: float, seconds_per_line: float, *, mode: RoundingMode = "round") -> int:
    if seconds_per_line <= 0:
        raise ValueError(f"seconds_per_line must be > 0, got {seconds_per_line}")
    x = t_sec / seconds_per_line
    if mode == "round":
        # Python round() is bankers-rounding; for GUI edits you usually want "round half away from zero".
        # We implement that explicitly:
        return int(floor(x + 0.5)) if x >= 0 else int(ceil(x - 0.5))
    if mode == "floor":
        return int(floor(x))
    if mode == "ceil":
        return int(ceil(x))
    raise ValueError(f"Unknown rounding mode: {mode}")


@dataclass(frozen=True)
class VelocityEvent:
    """A detected event in a 1D velocity trace.

    Canonical representation is index-based (i_*). Times (t_*) and duration are
    derived using seconds_per_line and are written to JSON for readability.

    Index i_* refers to the time axis (line number):
        t = i * seconds_per_line

    Notes on immutability:
      - Use with_* methods to create updated copies.
      - This avoids partial updates that can desynchronize redundant fields.
    """

    event_type: "EventType"

    # Canonical (required)
    i_start: int

    # Canonical (optional)
    i_peak: Optional[int] = None
    i_end: Optional[int] = None

    # Evidence (optional, depends on event_type)
    score_peak: Optional[float] = None
    baseline_before: Optional[float] = None
    baseline_after: Optional[float] = None

    # A single scalar for GUI sorting (larger = stronger evidence)
    strength: Optional[float] = None

    nan_fraction_in_event: Optional[float] = None
    n_valid_in_event: Optional[int] = None

    machine_type: "MachineType" = None  # you probably want MachineType.OTHER
    user_type: "UserType" = None        # you probably want UserType.UNREVIEWED
    note: str = ""

    # -----------------------
    # Derived time quantities
    # -----------------------

    def t_start(self, seconds_per_line: float) -> float:
        return float(self.i_start) * float(seconds_per_line)

    def t_peak(self, seconds_per_line: float) -> Optional[float]:
        return None if self.i_peak is None else float(self.i_peak) * float(seconds_per_line)

    def t_end(self, seconds_per_line: float) -> Optional[float]:
        return None if self.i_end is None else float(self.i_end) * float(seconds_per_line)

    def duration_sec(self, seconds_per_line: float) -> Optional[float]:
        if self.i_end is None:
            return None
        return (float(self.i_end) - float(self.i_start)) * float(seconds_per_line)

    # --------------------
    # Functional "updates"
    # --------------------

    def with_i_start(self, i_start: int) -> "VelocityEvent":
        return dataclasses.replace(self, i_start=int(i_start))

    def with_i_peak(self, i_peak: Optional[int]) -> "VelocityEvent":
        return dataclasses.replace(self, i_peak=None if i_peak is None else int(i_peak))

    def with_i_end(self, i_end: Optional[int]) -> "VelocityEvent":
        return dataclasses.replace(self, i_end=None if i_end is None else int(i_end))

    def with_t_start(
        self,
        t_start_sec: float,
        *,
        seconds_per_line: float,
        mode: RoundingMode = "round",
    ) -> "VelocityEvent":
        i_start = _time_to_index(float(t_start_sec), float(seconds_per_line), mode=mode)
        # Optional: maintain ordering constraints if end exists
        if self.i_end is not None and i_start > self.i_end:
            # If user drags start past end, you can either clamp or null end. Here: clamp start to end.
            i_start = self.i_end
        return dataclasses.replace(self, i_start=i_start)

    def with_t_peak(
        self,
        t_peak_sec: Optional[float],
        *,
        seconds_per_line: float,
        mode: RoundingMode = "round",
    ) -> "VelocityEvent":
        if t_peak_sec is None:
            return dataclasses.replace(self, i_peak=None)
        i_peak = _time_to_index(float(t_peak_sec), float(seconds_per_line), mode=mode)
        return dataclasses.replace(self, i_peak=i_peak)

    def with_t_end(
        self,
        t_end_sec: Optional[float],
        *,
        seconds_per_line: float,
        mode: RoundingMode = "round",
    ) -> "VelocityEvent":
        if t_end_sec is None:
            return dataclasses.replace(self, i_end=None)
        i_end = _time_to_index(float(t_end_sec), float(seconds_per_line), mode=mode)
        # Optional: enforce end >= start
        if i_end < self.i_start:
            i_end = self.i_start
        return dataclasses.replace(self, i_end=i_end)

    # -------------
    # Serialization
    # -------------

    def to_dict(self, *, seconds_per_line: float) -> dict[str, Any]:
        """Serialize to JSON-friendly dict.

        Writes canonical indices AND derived times/duration for readability.
        """
        d: dict[str, Any] = {
            "event_type": self.event_type.value if hasattr(self.event_type, "value") else self.event_type,
            "i_start": int(self.i_start),
            "i_peak": int(self.i_peak) if self.i_peak is not None else None,
            "i_end": int(self.i_end) if self.i_end is not None else None,
            "score_peak": float(self.score_peak) if self.score_peak is not None else None,
            "baseline_before": float(self.baseline_before) if self.baseline_before is not None else None,
            "baseline_after": float(self.baseline_after) if self.baseline_after is not None else None,
            "strength": float(self.strength) if self.strength is not None else None,
            "nan_fraction_in_event": float(self.nan_fraction_in_event) if self.nan_fraction_in_event is not None else None,
            "n_valid_in_event": int(self.n_valid_in_event) if self.n_valid_in_event is not None else None,
            "machine_type": self.machine_type.value if hasattr(self.machine_type, "value") else self.machine_type,
            "user_type": self.user_type.value if hasattr(self.user_type, "value") else self.user_type,
            "note": str(self.note),
        }

        # Derived, denormalized fields for human readability
        d["t_start"] = self.t_start(seconds_per_line)
        d["t_peak"] = self.t_peak(seconds_per_line)
        d["t_end"] = self.t_end(seconds_per_line)
        d["duration_sec"] = self.duration_sec(seconds_per_line)

        # Helpful for standalone interpretation (optional but nice)
        d["seconds_per_line"] = float(seconds_per_line)

        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VelocityEvent":
        """Deserialize from dict.

        Reads canonical fields (indices + evidence). Ignores derived fields:
        t_start/t_peak/t_end/duration_sec (and seconds_per_line if present).

        Assumes d['event_type'] etc. are stored as enum values.
        """
        # You probably want strict enum reconstruction here:
        event_type = d["event_type"]
        machine_type = d.get("machine_type")
        user_type = d.get("user_type")

        return cls(
            event_type=EventType(event_type) if "EventType" in globals() else event_type,
            i_start=int(d["i_start"]),
            i_peak=int(d["i_peak"]) if d.get("i_peak") is not None else None,
            i_end=int(d["i_end"]) if d.get("i_end") is not None else None,
            score_peak=float(d["score_peak"]) if d.get("score_peak") is not None else None,
            baseline_before=float(d["baseline_before"]) if d.get("baseline_before") is not None else None,
            baseline_after=float(d["baseline_after"]) if d.get("baseline_after") is not None else None,
            strength=float(d["strength"]) if d.get("strength") is not None else None,
            nan_fraction_in_event=float(d["nan_fraction_in_event"]) if d.get("nan_fraction_in_event") is not None else None,
            n_valid_in_event=int(d["n_valid_in_event"]) if d.get("n_valid_in_event") is not None else None,
            machine_type=MachineType(machine_type) if machine_type is not None and "MachineType" in globals() else machine_type,
            user_type=UserType(user_type) if user_type is not None and "UserType" in globals() else user_type,
            note=str(d.get("note", "")),
        )