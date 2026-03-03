"""Adapter layer for real kymograph access via the kymflow external facade.

This module is the single integration point used by the diameter-analysis
sandbox when working with real kymographs. It wraps facade APIs from
`kymflow.core.api.kym_external` and centralizes fixed defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from kymflow.core.api.kym_external import (
    get_channel_ids as _facade_get_channel_ids,
    get_kym_by_path as _facade_get_kym_by_path,
    get_kym_geometry as _facade_get_kym_geometry,
    get_kym_physical_size as _facade_get_kym_physical_size,
    get_roi_ids as _facade_get_roi_ids,
    get_roi_pixel_bounds as _facade_get_roi_pixel_bounds,
    load_kym_channel as _facade_load_kym_channel,
    load_kym_list as _facade_load_kym_list,
)

DEFAULT_CHANNEL_ID = 1
DEFAULT_ROI_ID = 1


def load_kym_list_for_folder(folder: str | Path) -> Any:
    """Load a kymograph list from a folder path.

    Args:
        folder: Folder path containing kymograph files.

    Returns:
        Kymograph list object returned by the facade.
    """
    return _facade_load_kym_list(folder)



def list_file_table_kym_images(klist: Any) -> list[Any]:
    """Return images for FileTableView.

    Trust the kymflow API: ``klist`` is expected to be a kym list object returned by
    ``load_kym_list_for_folder()`` / facade ``load_kym_list()``, and is assumed to
    already represent valid kymograph images.

    Returns:
        A plain list of image objects suitable for passing into
        ``FileTableView.set_files()``.
    """
    if klist is None:
        return []
    if not hasattr(klist, "images"):
        raise TypeError(
            f"Expected klist with .images (KymImageList contract); got {type(klist)!r}"
        )
    return list(klist.images)


def get_kym_by_path(klist: Any, path: str | Path) -> Any | None:
    """Get a kymograph object from a list by path.

    Args:
        klist: Kym list object returned by `load_kym_list_for_folder`.
        path: Candidate path to resolve.

    Returns:
        Matching kym object, or None when not found.
    """
    return _facade_get_kym_by_path(klist, path)


def iter_kym_items(klist: Any) -> list[Any]:
    """Return a materialized list of kym objects from a facade list object.

    Args:
        klist: Kym list object returned by `load_kym_list_for_folder`.

    Returns:
        List of kym objects.
    """
    images = getattr(klist, "images", None)
    if images is not None:
        return list(images)
    return list(klist)


def get_kym_geometry_for(kimg: Any) -> tuple[tuple[int, int], float, float]:
    """Get kymograph geometry and voxel units.

    Args:
        kimg: Kymograph object.

    Returns:
        Tuple `(shape, dt, dx)` where shape is `(num_lines, pixels_per_line)`.
    """
    return _facade_get_kym_geometry(kimg)


def get_kym_physical_size_for(kimg: Any) -> tuple[float, float]:
    """Get kymograph physical extents.

    Args:
        kimg: Kymograph object.

    Returns:
        Tuple `(duration_s, length_um)`.
    """
    return _facade_get_kym_physical_size(kimg)


def get_channel_ids_for(acq: Any) -> list[int]:
    """Get available channel IDs for an acquisition object.

    Args:
        acq: Acquisition/kymograph object.

    Returns:
        List of available channel IDs.
    """
    return _facade_get_channel_ids(acq)


def load_channel_for(acq: Any, channel: int = DEFAULT_CHANNEL_ID) -> np.ndarray:
    """Load and return channel data for an acquisition object.

    Args:
        acq: Acquisition/kymograph object.
        channel: 1-based channel ID. Defaults to `DEFAULT_CHANNEL_ID`.

    Returns:
        Loaded channel data.
    """
    return _facade_load_kym_channel(acq, int(channel))


def get_roi_ids_for(acq: Any) -> list[int]:
    """Get available ROI IDs for an acquisition object.

    Args:
        acq: Acquisition/kymograph object.

    Returns:
        List of ROI IDs.
    """
    return _facade_get_roi_ids(acq)


def get_roi_pixel_bounds_for(acq: Any, roi_id: int = DEFAULT_ROI_ID) -> Any:
    """Get ROI pixel bounds for an acquisition object.

    Args:
        acq: Acquisition/kymograph object.
        roi_id: ROI ID. Defaults to `DEFAULT_ROI_ID`.

    Returns:
        RoiPixelBounds facade object.
    """
    return _facade_get_roi_pixel_bounds(acq, int(roi_id))


def require_channel_and_roi(
    acq: Any,
    *,
    channel: int = DEFAULT_CHANNEL_ID,
    roi_id: int = DEFAULT_ROI_ID,
) -> None:
    """Validate that the required channel and ROI IDs exist.

    Args:
        acq: Acquisition/kymograph object.
        channel: Required channel ID.
        roi_id: Required ROI ID.

    Raises:
        ValueError: If required channel/ROI is missing.
    """
    channel_ids = get_channel_ids_for(acq)
    if int(channel) not in channel_ids:
        raise ValueError(
            f"Missing channel {int(channel)}. Available channels: {channel_ids or 'none'}."
        )

    roi_ids = get_roi_ids_for(acq)
    if int(roi_id) not in roi_ids:
        raise ValueError(f"Missing ROI {int(roi_id)}. Available ROI IDs: {roi_ids or 'none'}.")
