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
        bin_start: Starting bin number of the stall (first NaN bin).
            This represents the actual bin number (line scan bin) in the full
            image coordinate system. When detect_stalls() is called with
            start_bin=None (default), this is the array index (0-based).
            When start_bin is provided, this is the actual bin number
            (start_bin + array_index).
        bin_stop: Ending bin number of the stall (last NaN bin before next non-NaN).
            This represents the actual bin number (line scan bin) in the full
            image coordinate system, consistent with bin_start.
        stall_bins: Number of bins in the stall (bin_stop - bin_start + 1).
            This is the duration of the stall, and remains the same regardless
            of start_bin offset.
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
    min_stall_duration: int = 1,
    end_stall_non_nan_bins: int = 1,
    start_bin: int | None = None,
) -> list[Stall]:
    """Detect stalls in velocity array.

    A stall is a consecutive sequence of NaN values. A new stall can only
    start if we're past the refractory period (refactory_bins) from the
    last stall's stop bin. This prevents detecting overlapping or
    immediately adjacent stalls as separate events.

    Only stalls with duration >= min_stall_duration are included in the
    results. Stalls shorter than this threshold are filtered out and do not
    affect the refractory period.

    The bin_start and bin_stop values in the returned Stall objects represent
    the actual bin numbers (line scan bins) in the full image coordinate system.
    If start_bin is provided, array indices are offset by start_bin to get the
    actual bin numbers. If start_bin is None (default), bin values are the same
    as array indices (backward compatible behavior).

    Algorithm:
        1. Iterate through velocity array
        2. When encountering a NaN, check if we're past the refractory period
           from the last stall's stop bin (in array index space)
        3. If yes, mark as start of new stall and continue until finding a
           non-NaN value (end of stall)
        4. If stall duration >= min_stall_duration, add to results and update
           last_stall_stop for refractory period (in array index space)
        5. If stall duration < min_stall_duration, skip it (don't add to results,
           don't update refractory period)
        6. If no (within refractory period), skip this NaN
        7. Translate array indices to actual bin numbers using start_bin

    Args:
        velocity: 1D numpy array of velocity values (may contain NaN).
            Each element represents velocity at a specific bin (line scan).
        refactory_bins: Minimum number of bins between stall stop and next
            stall start. Must be >= 0. If 0, all consecutive stalls will be
            detected separately. Only accepted stalls (that pass min_stall_duration
            filter) affect the refractory period.
        min_stall_duration: Minimum number of bins (NaN and any bridged short non-NaN
            runs) required for a stall span to be included in results. Must be >= 1.
            Stalls with fewer total span bins than this are filtered out and do not
            affect the refractory period.
        end_stall_non_nan_bins: Number of consecutive non-NaN bins required to
            terminate an in-progress stall. This allows a stall to "bridge" short
            runs of valid (non-NaN) velocity values at its end (or within it): if a
            run of non-NaN values is shorter than this threshold, the stall will
            continue and include that short run in its overall span.
            Must be >= 1. Set to 1 for the original behavior (stall ends at the
            first non-NaN value).

        start_bin: Starting bin number for the first element of the velocity array.
            If None (default), bin values are the same as array indices (0-based).
            If provided, bin_start and bin_stop in returned Stall objects will be
            translated: actual_bin = start_bin + array_index.
            This allows Stall objects to represent actual bin numbers in the full
            image coordinate system when analyzing an ROI with start_time/stop_time.

    Returns:
        List of Stall objects, sorted by bin_start (ascending order).
        Empty list if no stalls are detected or all detected stalls are too short.
        The bin_start and bin_stop values represent actual bin numbers (offset by
        start_bin if provided).

    Raises:
        ValueError: If velocity is not 1D, refactory_bins is negative,
            min_stall_duration is less than 1, or start_bin is negative.

    Example:
        >>> velocity = np.array([1.0, 2.0, np.nan, np.nan, np.nan, 3.0, 4.0])
        >>> stalls = detect_stalls(velocity, refactory_bins=0, min_stall_duration=1)
        >>> len(stalls)
        1
        >>> stalls[0].bin_start
        2
        >>> stalls[0].bin_stop
        4
        >>> # With start_bin offset
        >>> stalls = detect_stalls(velocity, refactory_bins=0, min_stall_duration=1, start_bin=100)
        >>> stalls[0].bin_start
        102
        >>> stalls[0].bin_stop
        104
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
    if end_stall_non_nan_bins < 1:
        raise ValueError(
            f"end_stall_non_nan_bins must be >= 1, got {end_stall_non_nan_bins}"
        )
    if start_bin is None:
        start_bin = 0
    elif start_bin < 0:
        raise ValueError(f"start_bin must be >= 0, got {start_bin}")

    stalls: list[Stall] = []
    i = 0
    # Track last stall stop bin for refractory period check (in array index space)
    # Initialize to negative infinity so first stall can always start
    # Only accepted stalls (that pass min_stall_duration) update this
    last_stall_stop = -float("inf")

    # Iterate through velocity array
    while i < len(velocity):
        if np.isnan(velocity[i]):
            # Check if we're past refractory period from last accepted stall
            # If refactory_bins == 0, this condition is always True after first stall
            # Note: This comparison is in array index space, not actual bin space
            if i >= last_stall_stop + refactory_bins:
                # Start of potential new stall - we're past refractory period
                bin_start_idx = i

                # Continue until we see a sufficiently long run of non-NaN values.
                #
                # By default (end_stall_non_nan_bins == 1), this matches the original
                # behavior: the stall ends at the first non-NaN value.
                #
                # If end_stall_non_nan_bins > 1, short "bursts" of non-NaN values
                # (length < end_stall_non_nan_bins) are treated as part of the stall
                # span, allowing the stall to be extended/merged across those gaps.
                n_non_nan = 0
                last_nan_idx = bin_start_idx  # Track the last NaN index we've seen

                # Handle case where stall extends to end of array
                while i < len(velocity):
                    if np.isnan(velocity[i]):
                        # Update last NaN index - this is the current position
                        last_nan_idx = i
                        n_non_nan = 0
                        i += 1
                        continue

                    # non-NaN value
                    n_non_nan += 1
                    i += 1

                    # End the stall only once we've seen enough consecutive non-NaN bins
                    if n_non_nan >= end_stall_non_nan_bins:
                        break

                if i >= len(velocity):
                    # Stall extends to end of array
                    bin_stop_idx = len(velocity) - 1
                else:
                    # We terminated due to a qualifying run of non-NaN values.
                    # The stall ends at the last NaN we saw before this qualifying run.
                    bin_stop_idx = last_nan_idx

                # Total span (in bins) of the stall (may include short non-NaN bursts)
                stall_bins = bin_stop_idx - bin_start_idx + 1
                
                # Only accept stalls that meet minimum duration requirement.
                # min_stall_duration is based on the total number of bins in the stall span
                # (including any short non-NaN bursts that were bridged/ignored).
                if stall_bins >= min_stall_duration:
                    # Translate array indices to actual bin numbers
                    bin_start_actual = start_bin + bin_start_idx
                    bin_stop_actual = start_bin + bin_stop_idx
                    
                    stalls.append(
                        Stall(
                            bin_start=bin_start_actual,
                            bin_stop=bin_stop_actual,
                            stall_bins=stall_bins,
                        )
                    )
                    # Update refractory period tracker only for accepted stalls
                    # Keep this in array index space for internal algorithm
                    last_stall_stop = bin_stop_idx
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
