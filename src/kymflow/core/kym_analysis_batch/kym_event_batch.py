"""Kym-event batch helpers: ROI intersection and Radon prerequisites."""

from __future__ import annotations

from collections.abc import Sequence

from kymflow.core.image_loaders.kym_image import KymImage


def roi_intersection_across_files(files: Sequence[KymImage]) -> list[int]:
    """Return sorted ROI ids that exist in every file in ``files``.

    Args:
        files: Kymograph files to intersect (typically the filtered file-table subset).

    Returns:
        Sorted list of ROI ids present in all files. Empty if ``files`` is empty
        or there is no common ROI id.
    """
    if not files:
        return []
    sets = [set(f.rois.get_roi_ids()) for f in files]
    if not sets:
        return []
    inter = set.intersection(*sets)
    return sorted(inter)


def has_radon_velocity_and_time(kf: KymImage, roi_id: int, channel: int) -> bool:
    """Return True if Radon analysis has ``velocity`` and ``time`` for the ROI/channel.

    Kym event detection requires existing radon flow outputs for that pair.

    Args:
        kf: Kymograph file.
        roi_id: ROI identifier.
        channel: 1-based channel index.

    Returns:
        ``True`` if both arrays are available, else ``False``.
    """
    ka = kf.get_kym_analysis()
    radon = ka.get_analysis_object("RadonAnalysis")
    if radon is None:
        return False
    v = radon.get_analysis_value(roi_id, channel, "velocity", remove_outliers=False)
    t = radon.get_analysis_value(roi_id, channel, "time", remove_outliers=False)
    return v is not None and t is not None
