# kymflow/core/roi.py

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import TYPE_CHECKING, Any, Iterable

import numpy as np

if TYPE_CHECKING:
    # KymImage is used for type hints only - may not exist in all environments
    try:
        from kymflow.v2.core.image import KymImage
    except ImportError:
        # Fallback if v2 module doesn't exist
        KymImage = Any

@dataclass
class ROI:
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
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    def clamp_to_image(self, img: np.ndarray) -> None:
        """Clamp ROI to be fully inside the given image.

        This ensures that:
        * all coordinates are within [0, img.shape[1]] × [0, img.shape[0]]
        * left <= right and top <= bottom (by swapping coordinates if needed)

        Args:
            img: 2D numpy array.
        """
        self.left, self.top, self.right, self.bottom = clamp_coordinates(
            self.left, self.top, self.right, self.bottom, img
        )

    def clamp_to_bounds(self, img_w: int, img_h: int) -> None:
        """Clamp ROI to [0, img_w] × [0, img_h] and fix inverted edges.

        Args:
            img_w: Width of the image in pixels.
            img_h: Height of the image in pixels.
        """
        self.left, self.top, self.right, self.bottom = clamp_coordinates_to_size(
            self.left, self.top, self.right, self.bottom, img_w, img_h
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation of this ROI."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ROI":
        """Create a ROI from a dictionary produced by to_dict().

        Args:
            data: Dictionary with fields matching the ROI dataclass.
                Float coordinates will be converted to int.

        Returns:
            A new ROI instance initialized from the dictionary.
        """
        # Convert float coordinates to int if present
        for coord in ['left', 'top', 'right', 'bottom']:
            if coord in data and isinstance(data[coord], float):
                data[coord] = int(data[coord])
        return cls(**data)


class RoiSet:
    """Container and manager for multiple ROI instances.

    This class owns the ROIs, assigns unique integer IDs, and preserves
    creation order (via an internal dict).
    """

    def __init__(self) -> None:
        """Initialize an empty ROI set with an internal ID counter."""
        self._rois: dict[int, ROI] = {}
        self._next_id: int = 1

    def create_roi(
        self,
        left: int,
        top: int,
        right: int,
        bottom: int,
        name: str = "",
        note: str = "",
    ) -> ROI:
        """Create a new ROI, assign a unique id, and store it in the set.

        Args:
            left: Left coordinate in full-image pixels.
            top: Top coordinate in full-image pixels.
            right: Right coordinate in full-image pixels.
            bottom: Bottom coordinate in full-image pixels.
            name: Optional human-readable name.
            note: Optional free-form note.

        Returns:
            The newly created ROI instance.
        """
        roi = ROI(
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

    def get(self, roi_id: int) -> ROI | None:
        """Return the ROI with the given id, or None if not present.

        Args:
            roi_id: Identifier of the ROI to retrieve.

        Returns:
            The ROI instance or None.
        """
        return self._rois.get(roi_id)

    def __iter__(self) -> Iterable[ROI]:
        """Iterate over ROIs in creation order."""
        return iter(self._rois.values())

    def __len__(self) -> int:
        """Return the number of ROIs in the set."""
        return len(self._rois)

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize all ROIs to a list of dictionaries for JSON storage.

        Returns:
            A list of dictionaries, each compatible with `ROI.from_dict`.
        """
        return [roi.to_dict() for roi in self._rois.values()]

    @classmethod
    def from_list(cls, data: list[dict[str, Any]]) -> "RoiSet":
        """Create a ROI set from a list of ROI dictionaries.

        Args:
            data: List of dictionaries, each produced by `ROI.to_dict`.

        Returns:
            A new RoiSet containing all deserialized ROIs.
        """
        s = cls()
        for d in data:
            roi = ROI.from_dict(d)
            s._rois[roi.id] = roi
            s._next_id = max(s._next_id, roi.id + 1)
        return s


def clamp_coordinates(
    left: int, top: int, right: int, bottom: int,
    img: np.ndarray
) -> tuple[int, int, int, int]:
    """Clamp coordinates to be within bounds of img.shape (H, W).
    
    Args:
        left: Left coordinate.
        top: Top coordinate.
        right: Right coordinate.
        bottom: Bottom coordinate.
        img: 2D numpy array (enforces 2D).
    
    Returns:
        Tuple of (clamped_left, clamped_top, clamped_right, clamped_bottom) as int.
    
    Raises:
        ValueError: If img is not 2D.
    """
    if img.ndim != 2:
        raise ValueError(f"Expected a 2D image, got ndim {img.ndim}")
    
    height, width = img.shape
    
    def clamp(v: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, v))
    
    left = clamp(left, 0, width)
    right = clamp(right, 0, width)
    top = clamp(top, 0, height)
    bottom = clamp(bottom, 0, height)
    
    # Ensure non-inverted coordinates
    if left > right:
        left, right = right, left
    if top > bottom:
        top, bottom = bottom, top
    
    return left, top, right, bottom


def clamp_coordinates_to_size(
    left: int, top: int, right: int, bottom: int,
    img_w: int, img_h: int
) -> tuple[int, int, int, int]:
    """Clamp coordinates to [0, img_w] × [0, img_h] and fix inverted edges.
    
    Helper function for cases where we only have width/height metadata
    (e.g., loading from JSON without image data).
    
    Args:
        left: Left coordinate.
        top: Top coordinate.
        right: Right coordinate.
        bottom: Bottom coordinate.
        img_w: Width of the image in pixels.
        img_h: Height of the image in pixels.
    
    Returns:
        Tuple of (clamped_left, clamped_top, clamped_right, clamped_bottom) as int.
    """
    def clamp(v: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, v))
    
    left = clamp(left, 0, img_w)
    right = clamp(right, 0, img_w)
    top = clamp(top, 0, img_h)
    bottom = clamp(bottom, 0, img_h)
    
    # Ensure non-inverted coordinates
    if left > right:
        left, right = right, left
    if top > bottom:
        top, bottom = bottom, top
    
    return left, top, right, bottom


def roi_rect_is_equal(roi1: ROI, roi2: ROI) -> bool:
    """Check if two ROIs have the same coordinates.
    
    Compares only the coordinate fields (left, top, right, bottom),
    ignoring other fields like id, name, note.
    
    Args:
        roi1: First ROI to compare.
        roi2: Second ROI to compare.
    
    Returns:
        True if coordinates are equal, False otherwise.
    """
    return (
        roi1.left == roi2.left
        and roi1.top == roi2.top
        and roi1.right == roi2.right
        and roi1.bottom == roi2.bottom
    )


def point_in_roi(roi: ROI, x: int, y: int) -> bool:
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
    rois: RoiSet,
    x: int,
    y: int,
    edge_tol: int = 5,
) -> tuple[ROI | None, str | None]:
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
            roi: The hit ROI instance, or None if nothing was hit.
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
