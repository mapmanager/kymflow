# kymflow/core/roi.py

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable

import numpy as np

from .image import KymImage

@dataclass
class KymRoi:
    """Axis-aligned rectangular ROI in full-image pixel coordinates.

    Coordinates are expressed in the coordinate system of the full image
    (not the zoomed view). By convention:

    * left <= right
    * top  <= bottom

    These invariants are enforced by `clamp_to_image` (or `clamp_to_bounds`).
    """

    id: int
    name: str = ""
    note: str = ""
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0

    def clamp_to_image(self, image: KymImage) -> None:
        """Clamp ROI to be fully inside the given image.

        This ensures that:
        * all coordinates are within [0, image.width] × [0, image.height]
        * left <= right and top <= bottom (by swapping coordinates if needed)

        Args:
            image: KymImage providing width and height.
        """
        self.clamp_to_bounds(image.width, image.height)

    def clamp_to_bounds(self, img_w: int, img_h: int) -> None:
        """Clamp ROI to [0, img_w] × [0, img_h] and fix inverted edges.

        Args:
            img_w: Width of the image in pixels.
            img_h: Height of the image in pixels.
        """
        self.left = max(0, min(img_w, self.left))
        self.right = max(0, min(img_w, self.right))
        self.top = max(0, min(img_h, self.top))
        self.bottom = max(0, min(img_h, self.bottom))

        if self.left > self.right:
            self.left, self.right = self.right, self.left
        if self.top > self.bottom:
            self.top, self.bottom = self.bottom, self.top

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation of this ROI."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KymRoi":
        """Create a KymRoi from a dictionary produced by to_dict().

        Args:
            data: Dictionary with fields matching the KymRoi dataclass.

        Returns:
            A new KymRoi instance initialized from the dictionary.
        """
        return cls(**data)


class KymRoiSet:
    """Container and manager for multiple KymRoi instances.

    This class owns the ROIs, assigns unique integer IDs, and preserves
    creation order (via an internal dict).
    """

    def __init__(self) -> None:
        """Initialize an empty ROI set with an internal ID counter."""
        self._rois: dict[int, KymRoi] = {}
        self._next_id: int = 1

    def create_roi(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
        name: str = "",
        note: str = "",
    ) -> KymRoi:
        """Create a new ROI, assign a unique id, and store it in the set.

        Args:
            left: Left coordinate in full-image pixels.
            top: Top coordinate in full-image pixels.
            right: Right coordinate in full-image pixels.
            bottom: Bottom coordinate in full-image pixels.
            name: Optional human-readable name.
            note: Optional free-form note.

        Returns:
            The newly created KymRoi instance.
        """
        roi = KymRoi(
            id=self._next_id,
            name=name,
            note=note,
            left=left,
            top=top,
            right=right,
            bottom=bottom,
        )
        self._rois[roi.id] = roi
        self._next_id += 1
        return roi

    def delete(self, roi_id: int) -> None:
        """Remove the ROI with the given id, if it exists.

        Args:
            roi_id: Identifier of the ROI to remove.
        """
        self._rois.pop(roi_id, None)

    def get(self, roi_id: int) -> KymRoi | None:
        """Return the ROI with the given id, or None if not present.

        Args:
            roi_id: Identifier of the ROI to retrieve.

        Returns:
            The KymRoi instance or None.
        """
        return self._rois.get(roi_id)

    def __iter__(self) -> Iterable[KymRoi]:
        """Iterate over ROIs in creation order."""
        return iter(self._rois.values())

    def __len__(self) -> int:
        """Return the number of ROIs in the set."""
        return len(self._rois)

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize all ROIs to a list of dictionaries for JSON storage.

        Returns:
            A list of dictionaries, each compatible with `KymRoi.from_dict`.
        """
        return [roi.to_dict() for roi in self._rois.values()]

    @classmethod
    def from_list(cls, data: list[dict[str, Any]]) -> "KymRoiSet":
        """Create a ROI set from a list of ROI dictionaries.

        Args:
            data: List of dictionaries, each produced by `KymRoi.to_dict`.

        Returns:
            A new KymRoiSet containing all deserialized ROIs.
        """
        s = cls()
        for d in data:
            roi = KymRoi.from_dict(d)
            s._rois[roi.id] = roi
            s._next_id = max(s._next_id, roi.id + 1)
        return s


def point_in_roi(roi: KymRoi, x: float, y: float) -> bool:
    """Return True if point (x, y) lies inside or on the boundary of roi.

    Args:
        roi: ROI to test against.
        x: X coordinate in full-image pixels.
        y: Y coordinate in full-image pixels.

    Returns:
        True if the point is inside the ROI or on its edges, False otherwise.
    """
    return roi.left <= x <= roi.right and roi.top <= y <= roi.bottom


def hit_test_rois(
    rois: KymRoiSet,
    x: float,
    y: float,
    edge_tol: float = 5.0,
) -> tuple[KymRoi | None, str | None]:
    """Hit-test a collection of ROIs at point (x, y) in full-image coordinates.

    This function checks the four edges of each ROI with a tolerance and then
    the interior area. It iterates over ROIs in reverse creation order
    so that "topmost" (most recently created) ROIs are hit first.

    Args:
        rois: Collection of ROIs to test.
        x: X coordinate in full-image pixels.
        y: Y coordinate in full-image pixels.
        edge_tol: Tolerance in pixels to treat a point as "on an edge".

    Returns:
        A tuple (roi, mode) where:
            roi: The hit KymRoi instance, or None if nothing was hit.
            mode: One of:
                'resizing_left',
                'resizing_right',
                'resizing_top',
                'resizing_bottom',
                'moving',
                or None if no hit occurred.
    """
    # Reverse the creation order to hit "topmost" ROIs first.
    for roi in reversed(list(rois)):
        left = roi.left
        right = roi.right
        top = roi.top
        bottom = roi.bottom

        near_left = abs(x - left) <= edge_tol and top <= y <= bottom
        near_right = abs(x - right) <= edge_tol and top <= y <= bottom
        near_top = abs(y - top) <= edge_tol and left <= x <= right
        near_bottom = abs(y - bottom) <= edge_tol and left <= x <= right

        if near_left:
            return roi, "resizing_left"
        if near_right:
            return roi, "resizing_right"
        if near_top:
            return roi, "resizing_top"
        if near_bottom:
            return roi, "resizing_bottom"
        if point_in_roi(roi, x, y):
            return roi, "moving"

    return None, None
