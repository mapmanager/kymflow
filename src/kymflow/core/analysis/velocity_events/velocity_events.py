# velocity_events.py
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor
from enum import Enum
from typing import Literal, Optional, Sequence

import numpy as np


class MachineType(str, Enum):
    """Type assigned by the detector."""
    STALL_CANDIDATE = "stall_candidate"
    NAN_GAP = "nan_gap"
    REVERSAL_CANDIDATE = "reversal_candidate"  # abb, never used
    OTHER = "other"


class UserType(str, Enum):
    """Type assigned later by a human reviewer."""
    UNREVIEWED = "unreviewed"  # set in auto detect
    TRUE_STALL = "true_stall"  # set by user
    # RADON_FAILURE = "radon_failure"
    REVERSAL = "reversal"  # set by user
    # REJECT = "reject"
    OTHER = "other"  # set by user


EventType = Literal["baseline_drop", "nan_gap", "User Added"]  # abb added "User Added" for new events by user

RoundingMode = Literal["round", "floor", "ceil"]


def time_to_index(
    t_sec: float,
    seconds_per_line: float,
    *,
    mode: RoundingMode = "round",
) -> int:
    """Convert time in seconds to a line index using a rounding strategy.

    Rounds half away from zero for the default "round" mode.
    """
    if seconds_per_line <= 0:
        raise ValueError(f"seconds_per_line must be > 0, got {seconds_per_line}")
    x = t_sec / seconds_per_line
    if mode == "round":
        # Round half away from zero (avoid bankers-rounding for GUI edits).
        return int(floor(x + 0.5)) if x >= 0 else int(ceil(x - 0.5))
    if mode == "floor":
        return int(floor(x))
    if mode == "ceil":
        return int(ceil(x))
    raise ValueError(f"Unknown rounding mode: {mode}")


@dataclass(frozen=True)
class VelocityEvent:
    """A detected event in a 1D velocity trace.

    Indices refer to positions in the input arrays passed to the detector.
    Times are in seconds (from your CSV `time` column).
    Offsets (end) are optional; onset is the primary target.

    Workflow fields
    ---------------
    machine_type:
        Label assigned by the algorithm (e.g. STALL_CANDIDATE, NAN_GAP).
    user_type:
        Label assigned later by a human reviewer (default UNREVIEWED).
    note:
        Free text note field for later annotation.
    strength:
        Single scalar for GUI sorting (larger = stronger evidence). How it's computed
        depends on event type:
          - baseline_drop: (-score_peak) / threshold   (dimensionless)
          - nan_gap: nan_fraction_in_event * duration_sec
    """
    event_type: EventType

    # Onset (required)
    i_start: int
    t_start: float

    # Peak (optional but usually present for baseline_drop)
    i_peak: Optional[int] = None
    t_peak: Optional[float] = None

    # Offset (optional)
    i_end: Optional[int] = None
    t_end: Optional[float] = None

    # Evidence (optional, depends on event_type)
    score_peak: Optional[float] = None
    baseline_before: Optional[float] = None
    baseline_after: Optional[float] = None

    # A single scalar for GUI sorting (larger = stronger evidence)
    strength: Optional[float] = None

    nan_fraction_in_event: Optional[float] = None
    n_valid_in_event: Optional[int] = None
    duration_sec: Optional[float] = None

    machine_type: MachineType = MachineType.OTHER
    user_type: UserType = UserType.UNREVIEWED
    note: str = ""

    def to_dict(self, round_decimals: Optional[int] = None) -> dict:
        """Serialize to a JSON-friendly dictionary.

        Args:
            round_decimals: Number of decimal places to round to. If None, no rounding is done.
            
        Returns:
            Dictionary containing all VelocityEvent fields.
        """

        def _get_rounded_value(value: Optional[float], round_decimals: Optional[int] = None) -> Optional[float]:
            if value is None:
                return None
            if round_decimals is not None:
                return round(value, round_decimals)
            return value

        return {
            "event_type": self.event_type,

            "i_start": int(self.i_start),
            "i_peak": int(self.i_peak) if self.i_peak is not None else None,
            "i_end": int(self.i_end) if self.i_end is not None else None,
            
            "t_start": _get_rounded_value(self.t_start, round_decimals),
            "t_peak": _get_rounded_value(self.t_peak, round_decimals),
            "t_end": _get_rounded_value(self.t_end, round_decimals),
            
            "score_peak": _get_rounded_value(self.score_peak, round_decimals),

            "baseline_before": _get_rounded_value(self.baseline_before, round_decimals),
            "baseline_after": _get_rounded_value(self.baseline_after, round_decimals),

            "strength": _get_rounded_value(self.strength, round_decimals),

            "nan_fraction_in_event": float(self.nan_fraction_in_event) if self.nan_fraction_in_event is not None else None,
            "n_valid_in_event": int(self.n_valid_in_event) if self.n_valid_in_event is not None else None,

            "duration_sec": _get_rounded_value(self.duration_sec, round_decimals),
            # "duration_sec": float(self.duration_sec) if self.duration_sec is not None else None,
            
            "machine_type": self.machine_type.value,
            "user_type": self.user_type.value,
            "note": str(self.note),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VelocityEvent":
        """Deserialize from a dictionary.
        
        Args:
            d: Dictionary containing VelocityEvent fields.
            
        Returns:
            A VelocityEvent instance.
        """
        return cls(
            event_type=d["event_type"],
            i_start=int(d["i_start"]),
            t_start=float(d["t_start"]),
            i_peak=int(d["i_peak"]) if d.get("i_peak") is not None else None,
            t_peak=float(d["t_peak"]) if d.get("t_peak") is not None else None,
            i_end=int(d["i_end"]) if d.get("i_end") is not None else None,
            t_end=float(d["t_end"]) if d.get("t_end") is not None else None,
            score_peak=float(d["score_peak"]) if d.get("score_peak") is not None else None,
            baseline_before=float(d["baseline_before"]) if d.get("baseline_before") is not None else None,
            baseline_after=float(d["baseline_after"]) if d.get("baseline_after") is not None else None,
            strength=float(d["strength"]) if d.get("strength") is not None else None,
            nan_fraction_in_event=float(d["nan_fraction_in_event"]) if d.get("nan_fraction_in_event") is not None else None,
            n_valid_in_event=int(d["n_valid_in_event"]) if d.get("n_valid_in_event") is not None else None,
            duration_sec=float(d["duration_sec"]) if d.get("duration_sec") is not None else None,
            machine_type=MachineType(d.get("machine_type", MachineType.OTHER.value)),
            user_type=UserType(d.get("user_type", UserType.UNREVIEWED.value)),
            note=str(d.get("note", "")),
        )


def estimate_fs(time_s: np.ndarray) -> float:
    """Estimate sample rate from median dt in seconds."""
    dt = np.diff(time_s)
    dt = dt[np.isfinite(dt) & (dt > 0)]
    if dt.size == 0:
        raise ValueError("Cannot estimate sampling rate: time array has no positive finite diffs.")
    return 1.0 / float(np.median(dt))


def rolling_nanmedian(x: np.ndarray, w: int) -> np.ndarray:
    """Centered rolling nan-median. Simple O(n*w) implementation."""
    if w < 1:
        raise ValueError("w must be >= 1")
    if w % 2 == 0:
        w += 1
    n = x.size
    half = w // 2
    out = np.full(n, np.nan, dtype=float)
    for i in range(n):
        a = max(0, i - half)
        b = min(n, i + half + 1)
        out[i] = np.nanmedian(x[a:b])
    return out


def _group_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return inclusive [start,end] index runs where mask is True."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return []
    runs: list[tuple[int, int]] = []
    s = int(idx[0])
    prev = int(idx[0])
    for k in idx[1:]:
        k = int(k)
        if k == prev + 1:
            prev = k
            continue
        runs.append((s, prev))
        s = prev = k
    runs.append((s, prev))
    return runs


def _merge_runs_by_gap(runs: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    """Merge runs if the gap between them is <= max_gap samples."""
    if not runs:
        return []
    merged = [runs[0]]
    for s, e in runs[1:]:
        ps, pe = merged[-1]
        if s - pe - 1 <= max_gap:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def pick_topk_minima_indices(
    score: np.ndarray,
    time_s: np.ndarray,
    *,
    k: int,
    min_sep_sec: float,
) -> list[int]:
    """Pick up to k indices of the most negative score values, enforcing a time separation."""
    score = np.asarray(score, dtype=float)
    t = np.asarray(time_s, dtype=float)
    valid_idx = np.flatnonzero(np.isfinite(score))
    if valid_idx.size == 0:
        return []
    order = valid_idx[np.argsort(score[valid_idx])]  # most negative first

    fs = estimate_fs(t)
    min_sep = int(max(1, round(min_sep_sec * fs)))

    picked: list[int] = []
    occupied = np.zeros(score.size, dtype=bool)
    for i in order:
        if len(picked) >= k:
            break
        lo = max(0, int(i) - min_sep)
        hi = min(score.size, int(i) + min_sep + 1)
        if occupied[lo:hi].any():
            continue
        picked.append(int(i))
        occupied[lo:hi] = True
    picked.sort(key=lambda i: float(t[i]))
    return picked


def baseline_shift_score(
    time_s: np.ndarray,
    velocity: np.ndarray,
    *,
    win_cmp_sec: float = 0.25,
    min_valid_per_side: Optional[int] = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Compute score[i] = median(|v| right) - median(|v| left). NaNs ignored."""
    t = np.asarray(time_s, dtype=float)
    v = np.asarray(velocity, dtype=float)
    fs = estimate_fs(t)
    abs_v = np.abs(v)

    w_cmp = int(max(5, round(win_cmp_sec * fs)))
    if min_valid_per_side is None:
        min_valid_per_side = max(10, w_cmp // 5)

    n = v.size
    score = np.full(n, np.nan, dtype=float)
    medL = np.full(n, np.nan, dtype=float)
    medR = np.full(n, np.nan, dtype=float)

    for i in range(n):
        L = abs_v[max(0, i - w_cmp): i]
        R = abs_v[i: min(n, i + w_cmp)]
        if np.sum(np.isfinite(L)) >= min_valid_per_side and np.sum(np.isfinite(R)) >= min_valid_per_side:
            medL[i] = np.nanmedian(L)
            medR[i] = np.nanmedian(R)
            score[i] = medR[i] - medL[i]

    return score, medL, medR, fs


def detect_nan_gaps(
    time_s: Sequence[float],
    velocity: Sequence[float],
    *,
    nan_win_sec: float = 0.10,
    enter_frac: float = 0.40,
    exit_frac: float = 0.20,
    min_duration_sec: float = 0.02,
    merge_gap_sec: float = 0.05,
) -> list[VelocityEvent]:
    """Detect missing-evidence events where NaNs dominate a local time window.

    This detector treats NaNs as "missing evidence" and emits an event when the local
    density of NaNs becomes high enough (enter threshold), and ends the event when the
    NaN density falls back low enough (exit threshold). To avoid rapid on/off flicker,
    it uses hysteresis (enter_frac > exit_frac) plus optional merging of nearby runs.

    Args:
        time_s:
            1D array-like of timestamps in seconds, same length as `velocity`.
            Sampling is assumed approximately uniform; internal logic estimates sample
            rate `fs` from the median time step.
        velocity:
            1D array-like of velocity values. NaNs are interpreted as missing evidence.

        nan_win_sec:
            Window size (seconds) used to compute the local NaN fraction `nan_frac[i]`.
            For each sample i, nan_frac[i] is the mean of `is_nan` within a centered
            window of ~nan_win_sec around i.

            Larger values smooth the NaN fraction estimate and reduce sensitivity to
            brief NaN flicker (fewer false positives), but can smear short gaps.
            Smaller values react to brief NaN bursts and will produce more gap hits.

            **Most important knob for reducing false positives due to NaN flicker.**

        enter_frac:
            Enter threshold for starting a NaN-gap event.
            When `nan_frac[i] >= enter_frac`, the detector enters "gap" state.

            Higher values require denser NaNs to call a gap (fewer hits).
            Lower values call gaps more easily (more hits).

            **Most important knob for “how much NaN is enough to be a gap.”**

        exit_frac:
            Exit threshold for ending a NaN-gap event (hysteresis).
            When in gap state and `nan_frac[i] <= exit_frac`, the gap ends.

            Must generally be <= enter_frac. Lower values make gaps “stickier”
            (reduces rapid toggling and fragmentation). Higher values end gaps sooner
            (can create more fragments).

            Important primarily for reducing event fragmentation / flicker.

        min_duration_sec:
            Minimum duration (seconds) for an emitted NaN-gap event.
            After computing runs, any event shorter than this is discarded.

            Increase this to drop short blips (fewer false positives).

        merge_gap_sec:
            Merge adjacent NaN-gap runs that are separated by <= merge_gap_sec.
            This is applied after hysteresis classification.

            Increase this to combine fragmented gaps into fewer events.
            Decrease this to keep gaps separate.

    Returns:
        List[VelocityEvent]:
            Events with:
              - event_type="nan_gap"
              - machine_type=MachineType.NAN_GAP
              - i_start/t_start, i_end/t_end
              - duration_sec
              - nan_fraction_in_event (fraction NaN within the event span)
              - n_valid_in_event
              - strength = nan_fraction_in_event * duration_sec (simple severity proxy)

    How to tune (quick guidance):
        If you are getting too many NaN-gap hits:
          1) Increase `nan_win_sec` (smooths flicker; fewer on/off transitions)
          2) Increase `enter_frac` (requires denser NaNs to count as a gap)
          3) Increase `min_duration_sec` (drop short blips)
          4) Increase `merge_gap_sec` (combine fragmented hits into fewer events)
          5) Decrease `exit_frac` slightly (more hysteresis; less flicker)

        Recommended starting point for “fewer false positives”:
          nan_win_sec=0.20–0.40, enter_frac=0.60–0.80, exit_frac=0.30–0.50,
          min_duration_sec=0.05–0.10, merge_gap_sec=0.10–0.20
    """
    t = np.asarray(time_s, dtype=float)
    v = np.asarray(velocity, dtype=float)
    fs = estimate_fs(t)

    is_nan = ~np.isfinite(v)
    w = int(max(3, round(nan_win_sec * fs))) | 1
    half = w // 2

    nan_frac = np.zeros_like(v, dtype=float)
    n = v.size
    for i in range(n):
        a = max(0, i - half)
        b = min(n, i + half + 1)
        nan_frac[i] = float(np.mean(is_nan[a:b]))

    # hysteresis state machine
    in_gap = np.zeros(n, dtype=bool)
    state = False
    for i in range(n):
        if not state and nan_frac[i] >= enter_frac:
            state = True
        elif state and nan_frac[i] <= exit_frac:
            state = False
        in_gap[i] = state

    runs = _merge_runs_by_gap(_group_runs(in_gap), max_gap=int(max(0, round(merge_gap_sec * fs))))

    events: list[VelocityEvent] = []
    for s, e in runs:
        t_start = float(t[s])
        t_end = float(t[e])
        dur = float(t_end - t_start)
        if dur < min_duration_sec:
            continue
        seg = v[s:e+1]
        n_valid = int(np.sum(np.isfinite(seg)))
        nanf = float(1.0 - n_valid / seg.size) if seg.size else float("nan")
        events.append(
            VelocityEvent(
                event_type="nan_gap",
                i_start=int(s),
                t_start=t_start,
                i_end=int(e),
                t_end=t_end,
                duration_sec=dur,
                nan_fraction_in_event=nanf,
                n_valid_in_event=n_valid,
                machine_type=MachineType.NAN_GAP,
                strength=float(nanf * dur) if (np.isfinite(nanf) and np.isfinite(dur)) else None,
            )
        )
    return events


def detect_baseline_drops(
    time_s: Sequence[float],
    velocity: Sequence[float],
    *,
    win_cmp_sec: float = 0.25,
    smooth_sec: float = 0.05,
    min_valid_per_side: Optional[int] = None,
    mad_k: float = 3.0,
    abs_score_floor: float = 0.25,
    merge_gap_sec: float = 0.10,
    top_k_total: int = 6,
    min_sep_sec: float = 0.75,
) -> tuple[list[VelocityEvent], np.ndarray, np.ndarray, float]:
    """Detect candidate slowdowns/stalls as drops in baseline |velocity|.

    Sensitivity bias: after thresholding, we also ensure up to `top_k_total` candidates by
    adding the strongest negative-score minima (time-separated by `min_sep_sec`).
    """
    t = np.asarray(time_s, dtype=float)
    v = np.asarray(velocity, dtype=float)
    score, medL, medR, fs = baseline_shift_score(t, v, win_cmp_sec=win_cmp_sec, min_valid_per_side=min_valid_per_side)

    valid = np.isfinite(score)
    if np.sum(valid) < 50:
        return [], score, np.full_like(score, np.nan), float("nan")

    s = score[valid]
    med = float(np.median(s))
    mad = float(np.median(np.abs(s - med)))
    robust_sigma = 1.4826 * mad if mad > 0 else 0.0
    thresh = max(abs_score_floor, mad_k * robust_sigma)
    if not np.isfinite(thresh) or thresh <= 0:
        return [], score, np.full_like(score, np.nan), float("nan")

    abs_v = np.abs(v)
    w_smooth = int(max(3, round(smooth_sec * fs))) | 1
    abs_med = rolling_nanmedian(abs_v, w_smooth)

    drop_mask = (score <= -thresh) & valid
    runs = _merge_runs_by_gap(_group_runs(drop_mask), max_gap=int(round(merge_gap_sec * fs)))

    events: list[VelocityEvent] = []
    for r_start, r_end in runs:
        i_peak = int(r_start + np.nanargmin(score[r_start:r_end+1]))

        w_cmp = int(max(5, round(win_cmp_sec * fs)))
        L = abs_v[max(0, i_peak - w_cmp): i_peak]
        base_before = float(np.nanmedian(L)) if np.sum(np.isfinite(L)) >= max(10, w_cmp//5) else float(np.nanmedian(abs_v))
        low_level = 0.5 * base_before

        i_start = i_peak
        while i_start > 0 and np.isfinite(abs_med[i_start-1]) and abs_med[i_start-1] <= low_level:
            i_start -= 1

        events.append(
            VelocityEvent(
                event_type="baseline_drop",
                i_start=int(i_start),
                t_start=float(t[i_start]),
                i_peak=int(i_peak),
                t_peak=float(t[i_peak]),
                score_peak=float(score[i_peak]),
                baseline_before=float(medL[i_peak]) if np.isfinite(medL[i_peak]) else None,
                baseline_after=float(medR[i_peak]) if np.isfinite(medR[i_peak]) else None,
                machine_type=MachineType.STALL_CANDIDATE,
                strength=(float(-score[i_peak]) / float(thresh)) if (np.isfinite(thresh) and thresh > 0 and np.isfinite(score[i_peak])) else None,
            )
        )

    # Sensitivity-biased fallback
    if top_k_total is not None and top_k_total > 0 and len(events) < top_k_total:
        chosen_peaks = {e.i_peak for e in events if e.i_peak is not None}
        extra_peaks = pick_topk_minima_indices(score, t, k=top_k_total, min_sep_sec=min_sep_sec)
        for i_peak in extra_peaks:
            if i_peak in chosen_peaks:
                continue
            w_cmp = int(max(5, round(win_cmp_sec * fs)))
            L = abs_v[max(0, i_peak - w_cmp): i_peak]
            base_before = float(np.nanmedian(L)) if np.sum(np.isfinite(L)) >= max(10, w_cmp//5) else float(np.nanmedian(abs_v))
            low_level = 0.5 * base_before

            i_start = int(i_peak)
            while i_start > 0 and np.isfinite(abs_med[i_start-1]) and abs_med[i_start-1] <= low_level:
                i_start -= 1

            events.append(
                VelocityEvent(
                    event_type="baseline_drop",
                    i_start=int(i_start),
                    t_start=float(t[i_start]),
                    i_peak=int(i_peak),
                    t_peak=float(t[i_peak]),
                    score_peak=float(score[i_peak]),
                    baseline_before=float(medL[i_peak]) if np.isfinite(medL[i_peak]) else None,
                    baseline_after=float(medR[i_peak]) if np.isfinite(medR[i_peak]) else None,
                    machine_type=MachineType.STALL_CANDIDATE,
                    strength=(float(-score[i_peak]) / float(thresh)) if (np.isfinite(thresh) and thresh > 0 and np.isfinite(score[i_peak])) else None,
                )
            )

    events.sort(key=lambda e: (e.t_start, e.t_peak if e.t_peak is not None else e.t_start))
    return events, score, abs_med, float(thresh)


def detect_events(
    time_s: Sequence[float],
    velocity: Sequence[float],
    *,
    # baseline-drop params
    win_cmp_sec: float = 0.25,
    smooth_sec: float = 0.05,
    mad_k: float = 3.0,
    abs_score_floor: float = 0.25,
    merge_gap_sec: float = 0.10,
    top_k_total: int = 6,
    min_sep_sec: float = 0.75,
    # nan-gap params
    nan_win_sec: float = 0.10,
    nan_enter_frac: float = 0.40,
    nan_exit_frac: float = 0.20,
    nan_min_duration_sec: float = 0.02,
    nan_merge_gap_sec: float = 0.05,
) -> tuple[list[VelocityEvent], dict]:
    """
    Detect velocity “events” (candidate stalls/slowdowns + missing-evidence gaps) from a 1D velocity trace.

    Overview
    --------
    This function runs TWO detectors and returns a combined, time-sorted event list:

    (A) Baseline-drop detector (machine_type = STALL_CANDIDATE)
        Looks for a *drop in |velocity|* by comparing local baselines to the left and right of each timepoint.
        It produces events when the right-window baseline is substantially LOWER than the left-window baseline.

        Conceptually:
            score[i] = median(|v| in RIGHT window) - median(|v| in LEFT window)
        A slowdown/stall candidate corresponds to a large negative score.

    (B) NaN-gap detector (machine_type = NAN_GAP)
        Treats NaNs as “missing evidence,” but still detects transitions into/out of NaN-dominated regions.
        These events are useful because radon failures often cluster in time and correlate with stalls
        (or with images becoming un-analyzable).

    Inputs
    ------
    time_s:
        1D time array in seconds, same length as velocity.
        Sampling is assumed approximately uniform; internal code estimates fs from median dt.
    velocity:
        1D velocity array. May contain positive/negative values, zeros, and NaNs.

    Parameters (baseline-drop detector)
    ----------------------------------
    win_cmp_sec:
        Size (seconds) of the comparison windows on each side of a candidate boundary.
        For each index i, the detector compares |v| in:
            LEFT  = [i - win_cmp_sec, i)
            RIGHT = [i, i + win_cmp_sec]
        Larger values smooth out fast fluctuations (e.g. pulsation) but can smear short stalls.
        Smaller values increase sensitivity to brief changes but can increase false positives.

        *This is one of the most important parameters.*

    smooth_sec:
        Size (seconds) of the rolling median filter applied to |velocity| for onset localization.
        This does NOT decide whether an event exists; it mainly helps decide i_start (onset) by
        suppressing single-sample spikes / flicker.
        Larger -> smoother onset, fewer “one-sample pops”.
        Smaller -> more responsive onset.

        Moderately important (mostly affects onset placement, not detection count).

    mad_k:
        Threshold strength for baseline-drop detection using a robust scale estimate:
            threshold = max(abs_score_floor, mad_k * robust_sigma)
        where robust_sigma is derived from the MAD of the score distribution.
        Larger mad_k -> fewer baseline-drop events (more conservative).
        Smaller mad_k -> more baseline-drop events (more sensitive).

        *This is one of the most important parameters.*

    abs_score_floor:
        A hard minimum threshold for baseline-drop detection, expressed in the same units as velocity
        (because score is a difference of medians of |v|).
        This prevents the detector from “over-firing” when the signal is very low-variance and MAD is tiny.

        Important when you have very flat traces or low-variance recordings.

    merge_gap_sec:
        After thresholding, baseline-drop detections often form short “runs” of adjacent samples.
        This parameter merges nearby runs if their separation is <= merge_gap_sec.
        Larger -> fewer, longer events (merged).
        Smaller -> more fragmented events.

        Moderate importance (affects event fragmentation more than sensitivity).

    top_k_total:
        Sensitivity-biased “backstop”: if strict thresholding yields fewer than top_k_total events,
        the detector will add additional candidate peaks by selecting the most negative score minima,
        enforcing time separation (min_sep_sec).
        Setting this > 0 helps reduce false negatives, at the cost of some false positives.

        Very important if your philosophy is “prefer false positives over false negatives”.
        Set to 0 to disable the backstop.

    min_sep_sec:
        Minimum time separation between “extra” peaks chosen by the top-k fallback.
        Larger -> fewer clustered events.
        Smaller -> allows multiple nearby candidates.

        Moderate importance; mostly relevant if top_k_total > 0.

    Parameters (NaN-gap detector)
    -----------------------------
    nan_win_sec:
        Window size (seconds) used to compute local NaN fraction around each sample.
        Larger -> smoother NaN fraction estimate, fewer jittery transitions.
        Smaller -> more responsive to brief NaN bursts.

        Important if NaNs appear as single-sample flicker vs longer runs.

    nan_enter_frac:
        Enter threshold for NaN-gap “state machine”.
        If local NaN fraction >= nan_enter_frac, we enter a NaN-gap state.
        Higher -> requires denser NaNs to call a gap.
        Lower -> more sensitive to partial-missing regions.

        Important.

    nan_exit_frac:
        Exit threshold for NaN-gap state machine (hysteresis).
        If in gap state and local NaN fraction <= nan_exit_frac, we exit.
        Must be <= nan_enter_frac (recommended).
        Lower exit_frac makes gaps “stickier” (reduces flicker).

        Important.

    nan_min_duration_sec:
        Minimum duration for a NaN-gap event to be emitted.
        This prevents tiny NaN blips from becoming events.

        Moderate importance.

    nan_merge_gap_sec:
        Merge nearby NaN-gap runs separated by <= nan_merge_gap_sec.

        Moderate importance.

    “If I’m a biologist and I just want it to work…”
    ------------------------------------------------
    Start by tuning ONLY these, in this order:

      1) win_cmp_sec
         Controls the time-scale of what counts as a baseline change (stall/slowdown).
         Rough rule: pick something a bit longer than the oscillations you don’t want to trigger on
         (e.g. cardiac pulsation), but shorter than the stall durations you care about.

      2) mad_k  (and abs_score_floor if needed)
         Controls sensitivity. Lower = more candidates.

      3) top_k_total
         If you never want to miss events, keep this nonzero (e.g. 6–10).
         If you want “only high confidence”, set it to 0 or a small number.

    Everything else is mostly about *event cleanup* (merging, onset smoothing, NaN gap flicker control).

    Returns
    -------
    events:
        A time-sorted list of VelocityEvent objects.
        Expect mixed machine_type values:
          - MachineType.STALL_CANDIDATE  (event_type="baseline_drop")
          - MachineType.NAN_GAP          (event_type="nan_gap")

    debug:
        A dict of internal arrays and scalar thresholds useful for plotting and tuning.
        Current keys:

          debug["score"] : np.ndarray shape (N,)
              The baseline shift score at each sample:
                  score[i] = median(|v| right) - median(|v| left)
              More negative => stronger candidate slowdown.

          debug["abs_med"] : np.ndarray shape (N,)
              Rolling nan-median of |velocity| with window ~smooth_sec.
              Used mainly for onset localization and “visual sanity” plots.

          debug["threshold"] : float
              The baseline-drop threshold used for score (positive scalar).
              A baseline-drop candidate requires score <= -threshold.

        Notes:
          - These debug arrays are aligned to the input time/velocity samples.
          - They are intended for plotting (score vs time, abs_med vs time) and for diagnosing
            why a detector did/did not fire.
          - The debug dict is not required for downstream use; you can ignore it in production
            once parameters are tuned.
    """
    base_events, score, abs_med, thresh = detect_baseline_drops(
        time_s, velocity,
        win_cmp_sec=win_cmp_sec,
        smooth_sec=smooth_sec,
        mad_k=mad_k,
        abs_score_floor=abs_score_floor,
        merge_gap_sec=merge_gap_sec,
        top_k_total=top_k_total,
        min_sep_sec=min_sep_sec,
    )

    # abb 20260130, turn off nan_gap detection
    doNanGapDetection = False
    if doNanGapDetection:   
        nan_events = detect_nan_gaps(
            time_s, velocity,
            nan_win_sec=nan_win_sec,
            enter_frac=nan_enter_frac,
            exit_frac=nan_exit_frac,
            min_duration_sec=nan_min_duration_sec,
            merge_gap_sec=nan_merge_gap_sec,
        )
    else:
        nan_events = []

    events = sorted(base_events + nan_events, key=lambda e: e.t_start)

    debug = {"score": score, "abs_med": abs_med, "threshold": thresh}
    return events, debug
