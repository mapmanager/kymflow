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

    ROI names use str(roi_id) (e.g. "1", "2") so the view can select by name
    and map back to kymflow roi_id. kymflow uses int as the canonical ROI key.

    Args:
        kym: KymImage instance. Must have loaded channel data (call load_channel first).
        channel: 1-based channel index (default 1).

    Returns:
        (ChannelManager, List[RegionOfInterest]) for use with ImageRoiWidget.

    Raises:
        ValueError: If channel data cannot be loaded.
    """
    
    # logger.info('=== check for speed')
    
    # Lazy import to avoid pulling nicewidgets at module load when not needed
    from nicewidgets.image_line_widget.models import Channel, ChannelManager, RegionOfInterest

    # logger.warning(f'loading kym:{kym.path}')
    # logger.warning(f'  channel:{channel}')
    ok = kym.load_channel(channel)
    if not ok:
        raise ValueError(f"Failed to load channel {channel} for image {kym.path}")
    data = kym.getChannelData(channel)
    if data is None:
        raise ValueError(f"No data for channel {channel} after load")

    # Get geometry; fallback defaults if header incomplete
    try:
        (num_lines, pixels_per_line), dt, dx = get_kym_geometry(kym)
    except ValueError:
        raise ValueError(f"Failed to get_kym_geometry {channel} for image {kym.path}")
        # logger.error(f'error getting geometry for channel:{channel}')
        # num_lines, pixels_per_line = data.shape[0], data.shape[1]
        # dt = 0.001  # 1 ms/line default
        # dx = 1.0  # 1 um/pixel default

    x_label = kym.header.labels[0]
    y_label = kym.header.labels[1]
    # x_label = (
    #     kym.header.labels[0]
    #     # if kym.header.labels and len(kym.header.labels) >= 1
    #     # else "Time (s)"
    # )
    # y_label = (
    #     kym.header.labels[1]
    #     # if kym.header.labels and len(kym.header.labels) >= 2
    #     # else "Space (um)"
    # )

    _chanel_str = str(channel)

    # logger.warning(f'  num_lines:{num_lines}, pixels_per_line:{pixels_per_line}')
    # logger.warning(f'  dt:{dt}, dx:{dx}')
    # logger.warning(f'  x_label:{x_label}, y_label:{y_label}')
    # logger.warning(f'  _chanel_str:{_chanel_str}')

    # ch = Channel(name="Channel1", data=np.asarray(data))
    ch = Channel(name=_chanel_str, data=data)
    manager = ChannelManager(
        channels=[ch],
        row_scale=float(dt),
        col_scale=float(dx),
        x_label=x_label,
        y_label=y_label,
    )

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
