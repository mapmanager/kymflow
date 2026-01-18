"""Stall detection analysis for kymograph-derived signals.

This module detects "stalls" in per-ROI, per-bin signals (most commonly velocity
traces) produced by :class:`~kymflow.core.analysis.kym_analysis.KymAnalysis`.

A *stall* is a span of bins that begins at a NaN (missing) value in the signal.
During detection, short bursts of non-NaN values can be *bridged* (ignored) so
that a stall can extend through small "pops" of valid values. A stall is only
terminated once a sufficiently long consecutive run of non-NaN values is
observed.

This file also defines :class:`StallAnalysisParams` and :class:`StallAnalysis`
to support on-demand analysis and JSON persistence of both parameters and
results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

import numpy as np

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Stall:
    """Represents a detected stall span.

    Attributes:
        bin_start: Starting bin number of the stall (inclusive).
        bin_stop: Ending bin number of the stall (inclusive).
    """

    bin_start: int
    bin_stop: int

    def __post_init__(self) -> None:
        """Validate stall invariants."""
        if self.bin_start < 0:
            raise ValueError(f"bin_start must be >= 0, got {self.bin_start}")
        if self.bin_stop < self.bin_start:
            raise ValueError(
                f"bin_stop ({self.bin_stop}) must be >= bin_start ({self.bin_start})"
            )

    @property
    def stall_bins(self) -> int:
        """Total number of bins in the stall span (inclusive)."""
        return self.bin_stop - self.bin_start + 1

    def to_dict(self) -> Dict[str, int]:
        """Serialize to a JSON-friendly dictionary.

        Returns:
            Dictionary with keys: bin_start, bin_stop.
        """
        return {
            "bin_start": int(self.bin_start),
            "bin_stop": int(self.bin_stop),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Stall":
        """Deserialize from a dictionary.

        Args:
            d: Dictionary containing bin_start and bin_stop.

        Returns:
            A :class:`Stall` instance.

        Raises:
            KeyError: If required keys are missing.
            ValueError: If values are invalid.
        """
        bin_start = int(d["bin_start"])
        bin_stop = int(d["bin_stop"])
        return cls(bin_start=bin_start, bin_stop=bin_stop)


def detect_stalls(
    velocity: np.ndarray,
    refactory_bins: int,
    min_stall_duration: int = 1,
    end_stall_non_nan_bins: int = 1,
    start_bin: int | None = None,
) -> List[Stall]:
    """Detect stalls in a 1D signal array.

    A stall begins at a NaN value and continues until *end_stall_non_nan_bins*
    consecutive non-NaN values are observed. Shorter non-NaN runs are bridged,
    allowing a stall to extend through small bursts of valid values.

    The refractory period prevents a new stall from starting until
    *refactory_bins* bins have elapsed after the previous accepted stall.

    Note:
        ``min_stall_duration`` applies to the **total stall span length** in bins
        (NaN + any bridged non-NaN).

    Args:
        velocity: 1D array of signal values (typically velocity). NaNs mark missing.
        refactory_bins: Number of bins after an accepted stall during which new
            stalls are not allowed to start.
        min_stall_duration: Minimum stall span length (in bins) required to accept
            the stall.
        end_stall_non_nan_bins: Number of consecutive non-NaN bins required to
            terminate a stall. Use small values (2-4) to ignore brief non-NaN pops.
            Default 1 preserves the historical behavior.
        start_bin: Optional offset to translate array indices into "global" bin
            coordinates (e.g. line-scan bin indices in the full image). If None,
            bin numbers match array indices (0-based).

    Returns:
        List of accepted :class:`Stall` objects.

    Raises:
        ValueError: If parameters are invalid.
    """
    if velocity.ndim != 1:
        raise ValueError(f"velocity must be 1D array, got shape {velocity.shape}")
    if refactory_bins < 0:
        raise ValueError(f"refactory_bins must be >= 0, got {refactory_bins}")
    if min_stall_duration < 1:
        raise ValueError(f"min_stall_duration must be >= 1, got {min_stall_duration}")
    if end_stall_non_nan_bins < 1:
        raise ValueError(
            f"end_stall_non_nan_bins must be >= 1, got {end_stall_non_nan_bins}"
        )
    if start_bin is not None and int(start_bin) < 0:
        raise ValueError(f"start_bin must be >= 0, got {start_bin}")

    stalls: List[Stall] = []
    n = int(len(velocity))
    i = 0

    # Track the last accepted stall stop in *array index space*.
    last_stall_stop_idx = -refactory_bins - 1

    # Normalize offset for translating indices to bins.
    offset = int(start_bin) if start_bin is not None else 0

    while i < n:
        # Skip non-NaN values quickly.
        if not np.isnan(velocity[i]):
            i += 1
            continue

        # Enforce refractory period relative to the last *accepted* stall.
        if (i - last_stall_stop_idx) <= refactory_bins:
            i += 1
            continue

        # Found a candidate stall start at index i.
        stall_start_idx = i

        non_nan_run = 0  # consecutive non-NaN count since last NaN within current stall
        i += 1

        # Expand stall until termination criterion is met or we hit end of array.
        while i < n:
            if np.isnan(velocity[i]):
                # Reset termination counter on NaN.
                non_nan_run = 0
            else:
                non_nan_run += 1
                # Once we see enough consecutive non-NaNs, terminate stall.
                if non_nan_run >= end_stall_non_nan_bins:
                    break
            i += 1

        if i >= n:
            # Stall extends to end; include all remaining bins.
            stall_stop_idx = n - 1
        else:
            # i currently points to the last non-NaN in the terminating run (or later),
            # so exclude that terminating non-NaN run from the stall span.
            stall_stop_idx = i - non_nan_run

        stall_bins = stall_stop_idx - stall_start_idx + 1

        # Accept only if long enough (duration counts NaN + bridged non-NaN).
        if stall_bins >= min_stall_duration:
            bin_start_actual = offset + stall_start_idx
            bin_stop_actual = offset + stall_stop_idx
            stalls.append(
                Stall(
                    bin_start=bin_start_actual,
                    bin_stop=bin_stop_actual,
                )
            )
            last_stall_stop_idx = stall_stop_idx

        # Continue scanning from the end of the terminating non-NaN run (if any),
        # otherwise one bin past the stall stop.
        if i < n:
            i = stall_stop_idx + non_nan_run
        else:
            i = n

    return stalls


@dataclass(frozen=True)
class StallAnalysisParams:
    """Parameters controlling stall analysis.

    These parameters are intended to be persisted alongside results to ensure
    reproducibility.

    Attributes:
        velocity_key: Name of the analysis column/signal to analyze (e.g. 'velocity',
            'cleanVelocity', 'signedVelocity').
        refactory_bins: Refractory period after an accepted stall during which new stalls
            are not detected.
        min_stall_duration: Minimum accepted stall span length (in bins).
        end_stall_non_nan_bins: Number of consecutive non-NaN bins required to end a stall.
    """

    velocity_key: str = "velocity"
    refactory_bins: int = 0
    min_stall_duration: int = 1
    end_stall_non_nan_bins: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize parameters to a JSON-friendly dictionary."""
        return {
            "velocity_key": self.velocity_key,
            "refactory_bins": int(self.refactory_bins),
            "min_stall_duration": int(self.min_stall_duration),
            "end_stall_non_nan_bins": int(self.end_stall_non_nan_bins),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StallAnalysisParams":
        """Deserialize parameters from a dictionary."""
        return cls(
            velocity_key=str(d.get("velocity_key", "velocity")),
            refactory_bins=int(d.get("refactory_bins", 0)),
            min_stall_duration=int(d.get("min_stall_duration", 1)),
            end_stall_non_nan_bins=int(d.get("end_stall_non_nan_bins", 1)),
        )


@dataclass
class StallAnalysis:
    """Stall analysis results plus the parameters used to generate them.

    Attributes:
        params: Parameters used for detection and signal selection.
        stalls: List of detected stalls.
        analyzed_at: ISO-8601 timestamp (UTC) when this analysis was computed.
    """

    params: StallAnalysisParams
    stalls: List[Stall]
    analyzed_at: str

    @classmethod
    def run(
        cls,
        velocity: np.ndarray,
        params: StallAnalysisParams,
        *,
        start_bin: int | None = None,
    ) -> "StallAnalysis":
        """Run stall detection on a provided signal array.

        Args:
            velocity: 1D array of values to analyze (NaNs mark missing).
            params: Stall analysis parameters.
            start_bin: Optional offset to translate array indices to global bin numbers.

        Returns:
            A populated :class:`StallAnalysis` instance.
        """
        stalls = detect_stalls(
            velocity=velocity,
            refactory_bins=params.refactory_bins,
            min_stall_duration=params.min_stall_duration,
            end_stall_non_nan_bins=params.end_stall_non_nan_bins,
            start_bin=start_bin,
        )
        analyzed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return cls(params=params, stalls=stalls, analyzed_at=analyzed_at)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize results to a JSON-friendly dictionary."""
        return {
            "params": self.params.to_dict(),
            "stalls": [s.to_dict() for s in self.stalls],
            "analyzed_at": self.analyzed_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StallAnalysis":
        """Deserialize results from a dictionary.

        Args:
            d: Dictionary containing 'params' and optionally 'stalls' and 'analyzed_at'.

        Returns:
            A :class:`StallAnalysis` instance.
        """
        params = StallAnalysisParams.from_dict(d.get("params", {}))
        stalls = [Stall.from_dict(sd) for sd in d.get("stalls", [])]
        analyzed_at = str(d.get("analyzed_at", ""))
        return cls(params=params, stalls=stalls, analyzed_at=analyzed_at)
