"""External-facing helpers for working with kymograph images.

This module provides a small, strongly-typed facade over the core image loader
APIs (AcqImage, AcqImageList, KymImage, KymImageList). It encodes the
kymograph-specific assumptions about axes and voxel meanings so that external
callers (and LLMs) do not need to index header.shape and header.voxels manually.

Recommended guidance:

- When writing new analysis code that uses kym images, prefer the
  AcqImage / AcqImageList APIs (header, load_channel, getChannelData, find_by_path).
- Treat KymImage and KymImageList as concrete implementations, but do not
  depend on their additional convenience properties (num_lines, pixels_per_line,
  seconds_per_line, um_per_pixel) from external modules.
- Use the helpers in this module for geometry, channels, ROIs, and data in a
  consistent way.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.acq_image import AcqImage


# -----------------------------------------------------------------------------
# ROI bounds dataclasses (external-facing, simple row/col naming)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class RoiPixelBounds:
    """Pixel bounds for a rectangular ROI in image array coordinates.

    For 2D images: row = dimension 0 (height), col = dimension 1 (width).
    For kymographs: row = time axis, col = space axis.
    """

    row_start: int
    row_stop: int
    col_start: int
    col_stop: int


@dataclass(frozen=True)
class RoiPhysicalBounds:
    """ROI bounds in physical units (axis 0 and axis 1).

    Units depend on header.voxels_units. For kymographs, typically
    axis 0 = time (seconds), axis 1 = space (micrometers).
    """

    axis0_start: float
    axis0_stop: float
    axis1_start: float
    axis1_stop: float


def load_kym_list(path: str | Path) -> KymImageList:
    """Create a KymImageList from a folder/file/CSV path (no image data loaded).

    This is a convenience wrapper around KymImageList.load_from_path(). It
    constructs KymImage instances with load_image=False so that channel data
    is only loaded on demand.

    Args:
        path: Folder, file, or CSV path accepted by KymImageList.load_from_path().

    Returns:
        A KymImageList instance containing KymImage objects.
    """
    return KymImageList.load_from_path(path)


def get_kym_by_path(klist: KymImageList, path: str | Path) -> KymImage | None:
    """Find a KymImage in the list by its path using AcqImageList.find_by_path().

    This is the recommended way to look up a specific kymograph at runtime,
    rather than iterating and comparing paths manually.

    Args:
        klist: KymImageList to search.
        path: Absolute or relative path to the underlying TIFF file.

    Returns:
        The matching KymImage instance if found, or None if no match exists.
    """
    return klist.find_by_path(path)


def get_kym_geometry(acq: AcqImage) -> tuple[tuple[int, int], float, float]:
    """Return kymograph geometry and voxel sizes from an AcqImage.

    For kymographs, we adopt the following conventions:

    - header.shape == (num_lines, pixels_per_line)
      - axis 0 (rows) is time
      - axis 1 (columns) is space
    - header.voxels == (seconds_per_line, micrometers_per_pixel)

    This helper wraps those assumptions and returns:

    - shape: (num_lines, pixels_per_line)
    - dt: seconds per line (time axis voxel size)
    - dx: micrometers per pixel (space axis voxel size)

    Args:
        acq: An AcqImage or subclass instance representing a kymograph.

    Returns:
        (shape, dt, dx) where shape is (num_lines, pixels_per_line),
        dt is seconds per line, dx is micrometers per pixel.

    Raises:
        ValueError: If header.shape or header.voxels are missing or not
        compatible with the expected 2D kymograph semantics.
    """
    header = acq.header
    shape = header.shape
    vox = header.voxels

    if shape is None or len(shape) < 2:
        raise ValueError("Expected header.shape with at least 2 dimensions for kymograph.")
    if vox is None or len(vox) < 2:
        raise ValueError("Expected header.voxels with at least 2 entries for kymograph.")

    num_lines, pixels_per_line = int(shape[0]), int(shape[1])
    dt, dx = float(vox[0]), float(vox[1])
    return (num_lines, pixels_per_line), dt, dx


def get_kym_physical_size(acq: AcqImage) -> tuple[float, float]:
    """Return kymograph physical extents (duration and length) from an AcqImage.

    For kymographs we interpret axis 0 as time and axis 1 as space. This helper
    uses get_kym_geometry() to compute:

    - duration_s = num_lines * dt
    - length_um = pixels_per_line * dx

    Useful for plotting: set x-axis range to [0, length_um] and y-axis range
    to [0, duration_s] for space vs time display.

    Args:
        acq: An AcqImage or subclass instance representing a kymograph.

    Returns:
        (duration_s, length_um) where duration_s is total time in seconds and
        length_um is total scan length in micrometers.

    Raises:
        ValueError: Same as get_kym_geometry() if header is invalid.
    """
    (num_lines, pixels_per_line), dt, dx = get_kym_geometry(acq)
    duration_s = float(num_lines) * dt
    length_um = float(pixels_per_line) * dx
    return duration_s, length_um


def load_kym_channel(acq: AcqImage, channel: int) -> np.ndarray:
    """Ensure the given channel is loaded, then return its numpy array.

    This is a convenience wrapper around AcqImage.load_channel() and
    AcqImage.getChannelData() that enforces the lazy-loading pattern:

    1. Call acq.load_channel(channel) (no-op if already cached).
    2. Retrieve the data via acq.getChannelData(channel).

    Args:
        acq: An AcqImage or subclass instance.
        channel: 1-based channel index to load.

    Returns:
        A numpy array with the channel data.

    Raises:
        ValueError: If the channel could not be loaded or no data is available.
    """
    ok = acq.load_channel(channel)
    if not ok:
        raise ValueError(f"Failed to load channel {channel} for image {acq.path}")
    data = acq.getChannelData(channel)
    if data is None:
        raise ValueError(
            f"No data available for channel {channel} after load for image {acq.path}"
        )
    return data


# -----------------------------------------------------------------------------
# Channel API
# -----------------------------------------------------------------------------


def get_channel_ids(acq: AcqImage) -> list[int]:
    """Return available channel IDs (1-based integers) for the image.

    Channels can be loaded via load_channel() / load_kym_channel() and
    accessed via getChannelData().

    Args:
        acq: An AcqImage or subclass instance.

    Returns:
        Sorted list of channel IDs that have file paths or loaded data.
    """
    return acq.channels_available()


# -----------------------------------------------------------------------------
# ROI API (generic AcqImage)
# -----------------------------------------------------------------------------
#
# ROI identifier (roi_id):
# - kymflow uses int as the canonical ROI key.
# - The nicewidgets adapter maps roi_id to RegionOfInterest.name via str(roi_id)
#   (e.g. "1", "2") for display in ImageRoiWidget. Selection events provide the
#   name; use _parse_roi_id_from_name in image_line_viewer_v2_view to map back
#   to int (handles both "ROI_N" and bare "N" formats).


def get_roi_ids(acq: AcqImage) -> list[int]:
    """Return ROI IDs in creation order.

    ROIs are rectangular regions in the image. For KymImage (from KymImageList),
    metadata and ROIs are loaded automatically during construction. For other
    AcqImage subclasses, call acq.load_metadata() first if ROIs are needed.

    Args:
        acq: An AcqImage or subclass instance.

    Returns:
        List of ROI IDs.
    """
    return acq.rois.get_roi_ids()


def get_roi_pixel_bounds(acq: AcqImage, roi_id: int) -> RoiPixelBounds:
    """Return pixel bounds for an ROI.

    Args:
        acq: An AcqImage or subclass instance.
        roi_id: ROI identifier.

    Returns:
        RoiPixelBounds with row_start, row_stop, col_start, col_stop.

    Raises:
        ValueError: If ROI not found.
    """
    roi = acq.rois.get(roi_id)
    if roi is None:
        raise ValueError(f"ROI {roi_id} not found")
    b = roi.bounds
    return RoiPixelBounds(
        row_start=b.dim0_start,
        row_stop=b.dim0_stop,
        col_start=b.dim1_start,
        col_stop=b.dim1_stop,
    )


def get_roi_physical_bounds(acq: AcqImage, roi_id: int) -> RoiPhysicalBounds:
    """Return ROI bounds in physical units (using header.voxels).

    Args:
        acq: An AcqImage or subclass instance.
        roi_id: ROI identifier.

    Returns:
        RoiPhysicalBounds with axis0_start/stop, axis1_start/stop.
        For kymographs, axis0 = time (s), axis1 = space (um).

    Raises:
        ValueError: If ROI not found or header.voxels is None/incomplete.
    """
    rfb = acq.get_roi_physical_coords(roi_id)
    return RoiPhysicalBounds(
        axis0_start=rfb.dim0_start,
        axis0_stop=rfb.dim0_stop,
        axis1_start=rfb.dim1_start,
        axis1_stop=rfb.dim1_stop,
    )


def create_roi(
    acq: AcqImage,
    bounds: RoiPixelBounds | None = None,
    *,
    channel: int = 1,
    z: int = 0,
    name: str = "",
    note: str = "",
) -> RoiPixelBounds:
    """Create a new rectangular ROI.

    If bounds is None, creates an ROI encompassing the entire image.
    Coordinates are clamped to image bounds.

    Args:
        acq: An AcqImage or subclass instance.
        bounds: Optional pixel bounds. If None, uses full image.
        channel: Channel number (default 1).
        z: Slice/plane index (default 0). For 2D images, must be 0.
        name: Optional ROI name.
        note: Optional note.

    Returns:
        RoiPixelBounds of the created ROI (after clamping).

    Raises:
        ValueError: If channel or z is invalid.
    """
    from kymflow.core.image_loaders.roi import RoiBounds

    roi_bounds: RoiBounds | None = None
    if bounds is not None:
        roi_bounds = RoiBounds(
            dim0_start=bounds.row_start,
            dim0_stop=bounds.row_stop,
            dim1_start=bounds.col_start,
            dim1_stop=bounds.col_stop,
        )
    roi = acq.rois.create_roi(
        bounds=roi_bounds,
        channel=channel,
        z=z,
        name=name,
        note=note,
    )
    return RoiPixelBounds(
        row_start=roi.bounds.dim0_start,
        row_stop=roi.bounds.dim0_stop,
        col_start=roi.bounds.dim1_start,
        col_stop=roi.bounds.dim1_stop,
    )


def edit_roi(
    acq: AcqImage,
    roi_id: int,
    *,
    bounds: RoiPixelBounds | None = None,
    channel: int | None = None,
    z: int | None = None,
    name: str | None = None,
    note: str | None = None,
) -> RoiPixelBounds:
    """Edit an existing ROI.

    Args:
        acq: An AcqImage or subclass instance.
        roi_id: ROI identifier.
        bounds: New pixel bounds (optional).
        channel: New channel (optional).
        z: New slice index (optional).
        name: New name (optional).
        note: New note (optional).

    Returns:
        RoiPixelBounds of the updated ROI (after clamping).

    Raises:
        ValueError: If ROI not found or parameters invalid.
    """
    from kymflow.core.image_loaders.roi import RoiBounds

    roi_bounds: RoiBounds | None = None
    if bounds is not None:
        roi_bounds = RoiBounds(
            dim0_start=bounds.row_start,
            dim0_stop=bounds.row_stop,
            dim1_start=bounds.col_start,
            dim1_stop=bounds.col_stop,
        )
    acq.rois.edit_roi(
        roi_id,
        bounds=roi_bounds,
        channel=channel,
        z=z,
        name=name,
        note=note,
    )
    return get_roi_pixel_bounds(acq, roi_id)


def delete_roi(acq: AcqImage, roi_id: int) -> None:
    """Delete an ROI.

    Args:
        acq: An AcqImage or subclass instance.
        roi_id: ROI identifier to remove.
    """
    acq.rois.delete(roi_id)
