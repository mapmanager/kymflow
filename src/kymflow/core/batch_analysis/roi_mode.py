"""Shared ROI-mode helpers for batch strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from kymflow.core.image_loaders.kym_image import KymImage


@dataclass(frozen=True, slots=True)
class ResolvedRoi:
    """Resolved ROI for one file in a batch."""

    roi_id: int | None
    skip_message: str | None = None


def resolve_effective_roi(
    kf: KymImage,
    *,
    roi_mode: Literal["existing", "new_full_image"],
    roi_id: int | None,
) -> ResolvedRoi:
    """Resolve ROI for one file using shared batch ROI-mode rules.

    Args:
        kf: File being processed.
        roi_mode: Shared existing ROI or create full-image ROI per file.
        roi_id: ROI id when ``roi_mode == "existing"``.

    Returns:
        ``ResolvedRoi`` with ``roi_id`` on success, or ``skip_message`` when
        this file should be skipped.
    """
    if roi_mode == "new_full_image":
        roi = kf.rois.create_roi()
        return ResolvedRoi(roi_id=roi.id)

    if roi_id is None:
        return ResolvedRoi(roi_id=None, skip_message="no ROI id")

    if roi_id not in kf.rois.get_roi_ids():
        return ResolvedRoi(roi_id=None, skip_message=f"ROI {roi_id} not in file")

    return ResolvedRoi(roi_id=roi_id)


def preview_resolve_effective_roi(
    kf: KymImage,
    *,
    roi_mode: Literal["existing", "new_full_image"],
    roi_id: int | None,
) -> ResolvedRoi:
    """Resolve ROI for batch preview without creating ROIs.

    For ``new_full_image``, returns ``ResolvedRoi(roi_id=None, skip_message=None)``
    to indicate a ROI would be created at run time (not a skip). Downstream preview
    logic must not assert ``roi_id`` is set in that case.

    Args:
        kf: File being previewed.
        roi_mode: Shared existing ROI or create full-image ROI per file at run time.
        roi_id: ROI id when ``roi_mode == \"existing\"``.

    Returns:
        Same shape as :func:`resolve_effective_roi`, but never calls
        :meth:`~kymflow.core.image_loaders.roi.RoiSet.create_roi`.
    """
    if roi_mode == "new_full_image":
        return ResolvedRoi(roi_id=None, skip_message=None)
    if roi_id is None:
        return ResolvedRoi(roi_id=None, skip_message="no ROI id")
    if roi_id not in kf.rois.get_roi_ids():
        return ResolvedRoi(roi_id=None, skip_message=f"ROI {roi_id} not in file")
    return ResolvedRoi(roi_id=roi_id)
