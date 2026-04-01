"""Adapter functions for mapping kymflow models to nicewidgets models.

Phase 2 of the migration plan: KymImage-to-ChannelManager and
VelocityEvent-to-AcqImageEvent conversion.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List, Optional

import numpy as np

from kymflow.core.api.kym_external import get_kym_geometry, get_roi_ids, get_roi_pixel_bounds
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.config import MAX_NUM_ROI

if TYPE_CHECKING:
    from kymflow.core.analysis.velocity_events.velocity_events import VelocityEvent

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

def kymimage_to_channel_manager(
    kym: KymImage,
    channel: int = 1,
) -> tuple["ChannelManager", List["RegionOfInterest"]]:
    """Build ChannelManager and RegionOfInterest list from a KymImage.

    Handles transpose and physical units. KymImage uses (rows=time, cols=space).
    ChannelManager row_scale = seconds_per_line, col_scale = micrometers_per_pixel.

    All loadable channels (see ``channels_available()``) are placed in the manager
    so nicewidgets can enable the contrast channel ``ui.select`` when there is
    more than one. The active channel is ``channel`` if that channel loaded,
    otherwise the first loadable channel.

    ROI names use str(roi_id) (e.g. "1", "2") so the view can select by name
    and map back to kymflow roi_id. kymflow uses int as the canonical ROI key.

    Args:
        kym: KymImage instance.
        channel: 1-based channel index to mark active in the manager (default 1).

    Returns:
        (ChannelManager, List[RegionOfInterest]) for use with ImageRoiWidget.

    Raises:
        ValueError: If no channel data could be loaded or geometry is invalid.
    """
    # Lazy import to avoid pulling nicewidgets at module load when not needed
    from nicewidgets.image_line_widget.models import Channel, ChannelManager, RegionOfInterest

    channel_keys = kym.channels_available()
    if not channel_keys:
        raise ValueError(f"No channels available for image {kym.path}")

    channels_list: List[Channel] = []
    for ch_num in sorted(channel_keys):
        ok = kym.load_channel(ch_num)
        if not ok:
            logger.warning(f"Skipping channel {ch_num}: load failed for {kym.path}")
            continue
        data = kym.getChannelData(ch_num)
        if data is None:
            logger.warning(f"Skipping channel {ch_num}: no data after load for {kym.path}")
            continue
        channels_list.append(Channel(name=str(ch_num), data=np.asarray(data)))

    if not channels_list:
        raise ValueError(f"No channel data could be loaded for image {kym.path}")

    # Get geometry; fallback defaults if header incomplete
    try:
        (_num_lines, _pixels_per_line), dt, dx = get_kym_geometry(kym)
    except ValueError:
        raise ValueError(f"Failed to get_kym_geometry for image {kym.path}")

    x_label = kym.header.labels[0]
    y_label = kym.header.labels[1]

    manager = ChannelManager(
        channels=channels_list,
        row_scale=float(dt),
        col_scale=float(dx),
        x_label=x_label,
        y_label=y_label,
    )
    loaded_names = {c.name for c in channels_list}
    active_name = str(channel) if str(channel) in loaded_names else channels_list[0].name
    manager.active_channel_name = active_name

    rois: List[RegionOfInterest] = []
    for roi_id in get_roi_ids(kym):
        bounds = get_roi_pixel_bounds(kym, roi_id)
        roi = RegionOfInterest(
            name=f"{roi_id}",
            r0=bounds.row_start,
            r1=bounds.row_stop,
            c0=bounds.col_start,
            c1=bounds.col_stop,
        )
        rois.append(roi)

    return manager, rois


def create_full_roi_for_widget(kym: KymImage) -> "RegionOfInterest | None":
    """Create a full-image ROI in kymflow and return RegionOfInterest for ImageRoiWidget.

    Used when ImageRoiWidget Add button is clicked and on_request_add_roi callback
    delegates to kymflow. Returns None if no file, max ROIs reached, or creation fails.

    Args:
        kym: KymImage to create ROI in.

    Returns:
        RegionOfInterest with name=str(roi_id), or None on failure.
    """
    from nicewidgets.image_line_widget.models import RegionOfInterest

    if MAX_NUM_ROI is not None:
        n = kym.rois.numRois()
        if n >= MAX_NUM_ROI:
            logger.warning(
                "create_full_roi_for_widget: max ROIs reached (%d >= %d)",
                n,
                MAX_NUM_ROI,
            )
            return None
    try:
        roi = kym.rois.create_roi(bounds=None)
        bounds = get_roi_pixel_bounds(kym, roi.id)
        return RegionOfInterest(
            name=str(roi.id),
            r0=bounds.row_start,
            r1=bounds.row_stop,
            c0=bounds.col_start,
            c1=bounds.col_stop,
        )
    except ValueError as exc:
        logger.warning("create_full_roi_for_widget: %s", exc)
        return None


def velocity_events_to_acq_image_events(
    events: Optional[List["VelocityEvent"]],
) -> List["AcqImageEvent"]:
    """Convert kymflow VelocityEvent list to nicewidgets AcqImageEvent list.

    Maps t_start/t_end, event_type, user_type, and _uuid (event_id).

    Args:
        events: List of VelocityEvent, or None (returns empty list).

    Returns:
        List of AcqImageEvent for use with LinePlotWidget.acq_image_events.
    """
    from nicewidgets.image_line_widget.models import AcqImageEvent

    if events is None:
        return []

    result = []
    for ev in events:
        event_id = (
            getattr(ev, "_uuid", None)
            if hasattr(ev, "_uuid")
            else None
        )
        if event_id is None:
            event_id = str(uuid.uuid4())
        acq = AcqImageEvent(
            start_t=float(ev.t_start),
            stop_t=float(ev.t_end) if ev.t_end is not None else None,
            event_type=str(ev.event_type),
            user_type=getattr(ev.user_type, "value", str(ev.user_type)),
            event_id=event_id,
        )
        result.append(acq)
    return result
