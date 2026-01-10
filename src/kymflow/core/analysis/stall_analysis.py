"""Stall detection analysis for kymograph velocity data.

This module provides functionality to detect "stalls" in velocity arrays.
A stall is defined as a consecutive sequence of NaN (missing) values in
the velocity data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Stall:
    """Represents a detected stall in velocity data.

    A stall is a consecutive sequence of NaN values in the velocity array.
    The stall spans from bin_start (inclusive) to bin_stop (inclusive).

    Attributes:
        bin_start: Starting bin index of the stall (first NaN bin).
        bin_stop: Ending bin index of the stall (last NaN bin before next non-NaN).
        stall_bins: Number of bins in the stall (bin_stop - bin_start + 1).
    """

    bin_start: int
    bin_stop: int
    stall_bins: int

    def __post_init__(self) -> None:
        """Validate stall data after initialization."""
        if self.bin_start < 0:
            raise ValueError(f"bin_start must be >= 0, got {self.bin_start}")
        if self.bin_stop < self.bin_start:
            raise ValueError(
                f"bin_stop ({self.bin_stop}) must be >= bin_start ({self.bin_start})"
            )
        if self.stall_bins != (self.bin_stop - self.bin_start + 1):
            raise ValueError(
                f"stall_bins ({self.stall_bins}) must equal "
                f"(bin_stop - bin_start + 1) = ({self.bin_stop - self.bin_start + 1})"
            )


def detect_stalls(
    velocity: np.ndarray,
    refactory_bins: int,
    min_stall_duration: int = 1
) -> list[Stall]:
    """Detect stalls in velocity array.

    A stall is a consecutive sequence of NaN values. A new stall can only
    start if we're past the refractory period (refactory_bins) from the
    last stall's stop bin. This prevents detecting overlapping or
    immediately adjacent stalls as separate events.

    Only stalls with duration >= min_stall_duration are included in the
    results. Stalls shorter than this threshold are filtered out and do not
    affect the refractory period.

    Algorithm:
        1. Iterate through velocity array
        2. When encountering a NaN, check if we're past the refractory period
           from the last stall's stop bin
        3. If yes, mark as start of new stall and continue until finding a
           non-NaN value (end of stall)
        4. If stall duration >= min_stall_duration, add to results and update
           last_stall_stop for refractory period
        5. If stall duration < min_stall_duration, skip it (don't add to results,
           don't update refractory period)
        6. If no (within refractory period), skip this NaN

    Args:
        velocity: 1D numpy array of velocity values (may contain NaN).
            Each element represents velocity at a specific bin (line scan).
        refactory_bins: Minimum number of bins between stall stop and next
            stall start. Must be >= 0. If 0, all consecutive stalls will be
            detected separately. Only accepted stalls (that pass min_stall_duration
            filter) affect the refractory period.
        min_stall_duration: Minimum number of bins required for a stall to be
            included in results. Must be >= 1. Stalls shorter than this are
            filtered out and do not affect the refractory period.

    Returns:
        List of Stall objects, sorted by bin_start (ascending order).
        Empty list if no stalls are detected or all detected stalls are too short.

    Raises:
        ValueError: If velocity is not 1D, refactory_bins is negative, or
            min_stall_duration is less than 1.

    Example:
        >>> velocity = np.array([1.0, 2.0, np.nan, np.nan, np.nan, 3.0, 4.0])
        >>> stalls = detect_stalls(velocity, refactory_bins=0, min_stall_duration=1)
        >>> len(stalls)
        1
        >>> stalls[0].bin_start
        2
        >>> stalls[0].bin_stop
        4
        >>> # Filter out short stalls
        >>> stalls = detect_stalls(velocity, refactory_bins=0, min_stall_duration=5)
        >>> len(stalls)
        0
    """
    # Validate inputs
    if velocity.ndim != 1:
        raise ValueError(f"velocity must be 1D array, got shape {velocity.shape}")
    if refactory_bins < 0:
        raise ValueError(f"refactory_bins must be >= 0, got {refactory_bins}")
    if min_stall_duration < 1:
        raise ValueError(
            f"min_stall_duration must be >= 1, got {min_stall_duration}"
        )

    stalls: list[Stall] = []
    i = 0
    # Track last stall stop bin for refractory period check
    # Initialize to negative infinity so first stall can always start
    # Only accepted stalls (that pass min_stall_duration) update this
    last_stall_stop = -float("inf")

    # Iterate through velocity array
    while i < len(velocity):
        if np.isnan(velocity[i]):
            # Check if we're past refractory period from last accepted stall
            # If refactory_bins == 0, this condition is always True after first stall
            if i >= last_stall_stop + refactory_bins:
                # Start of potential new stall - we're past refractory period
                bin_start = i

                # Continue until we find a non-NaN value (end of stall)
                # Handle case where stall extends to end of array
                while i < len(velocity) and np.isnan(velocity[i]):
                    i += 1

                # bin_stop is the last NaN bin before the next valid value
                # If stall goes to end of array, bin_stop is last index
                bin_stop = i - 1
                stall_bins = bin_stop - bin_start + 1

                # Only accept stalls that meet minimum duration requirement
                if stall_bins >= min_stall_duration:
                    stalls.append(
                        Stall(
                            bin_start=bin_start,
                            bin_stop=bin_stop,
                            stall_bins=stall_bins,
                        )
                    )
                    # Update refractory period tracker only for accepted stalls
                    last_stall_stop = bin_stop
                # If stall is too short, skip it (don't add to results,
                # don't update last_stall_stop, so it doesn't affect refractory period)
            else:
                # Skip this NaN - we're within refractory period of last accepted stall
                # Just move past it without creating a new stall
                i += 1
        else:
            # Non-NaN value - just continue
            i += 1

    return stalls
