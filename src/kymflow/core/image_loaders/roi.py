# kymflow/core/image_loaders/roi.py

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import TYPE_CHECKING, Any, Iterable

import numpy as np

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    # KymImage is used for type hints only - may not exist in all environments
    try:
        from kymflow.v2.core.image import KymImage
    except ImportError:
        # Fallback if v2 module doesn't exist
        KymImage = Any
    from kymflow.core.image_loaders.acq_image import AcqImage

@dataclass
class ROI:
    """Axis-aligned rectangular ROI in full-image pixel coordinates.

    Coordinates are expressed in the coordinate system of the full image
    (not the zoomed view). By convention:

    * left <= right
    * top  <= bottom

    These invariants are enforced by `clamp_to_image` (or `clamp_to_bounds`).
    
    Each ROI is associated with a specific channel and z (plane/slice) coordinate.
    For 2D images, z is always 0. For 3D images, z is in [0, num_slices-1].
    """

    id: int
    channel: int = 1
    z: int = 0
    name: str = ""
    note: str = ""
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0
    # Increments when ROI geometry (or channel/z) changes. Used to mark analysis as stale.
    revision: int = 0

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
                Missing channel/z will default to 1/0 for backward compatibility.

        Returns:
            A new ROI instance initialized from the dictionary.
        """
        # Work on a copy so we don't mutate the caller's dict.
        data = dict(data)

        # Convert float coordinates to int if present
        for coord in ['left', 'top', 'right', 'bottom', 'channel', 'z']:
            if coord in data and isinstance(data[coord], float):
                data[coord] = int(data[coord])
        
        # Backward compatibility: default channel=1, z=0 if not present
        if 'channel' not in data:
            data['channel'] = 1
        if 'z' not in data:
            data['z'] = 0

        # Backward compatibility: default revision to 0 if not present
        if 'revision' not in data:
            data['revision'] = 0
        
        return cls(**data)


class RoiSet:
    """Container and manager for multiple ROI instances.

    This class owns the ROIs, assigns unique integer IDs, and preserves
    creation order (via an internal dict). Holds a reference to AcqImage
    for bounds validation.
    """

    def __init__(self, acq_image: "AcqImage") -> None:
        """Initialize an empty ROI set with an internal ID counter.
        
        Args:
            acq_image: Reference to AcqImage instance for bounds validation.
        """
        self.acq_image = acq_image
        self._rois: dict[int, ROI] = {}
        self._next_id: int = 1
    
    def _get_bounds(self) -> tuple[int, int, int]:
        """Get image bounds (width, height, num_slices) for validation.
        
        Queries bounds from AcqImage header. All channels share the same shape.
        Bounds are never stored in RoiSet.
        
        Returns:
            Tuple of (img_w, img_h, num_slices).
            
        Raises:
            ValueError: If bounds cannot be determined (shape is None).
        """
        shape = self.acq_image.img_shape
        if shape is None:
            raise ValueError(
                "Cannot determine image bounds: header.shape is None. "
                "Image data must be loaded or header must be populated."
            )
        
        ndim = self.acq_image.img_ndim
        if ndim is None:
            raise ValueError(
                "Cannot determine image bounds: header.ndim is None. "
                "Image data must be loaded or header must be populated."
            )
        
        if ndim == 2:
            img_h, img_w = shape
            num_slices = 1
        elif ndim == 3:
            num_slices, img_h, img_w = shape
        else:
            raise ValueError(f"Unsupported image ndim: {ndim} (must be 2 or 3)")
        
        return (img_w, img_h, num_slices)
    
    def _validate_channel(self, channel: int) -> None:
        """Validate that channel exists in AcqImage.
        
        Args:
            channel: Channel number to validate.
            
        Raises:
            ValueError: If channel doesn't exist.
        """
        channel_keys = self.acq_image.getChannelKeys()
        if channel_keys and channel in channel_keys:
            return
        
        # Also check _file_path_dict for channels that may not have loaded data
        if hasattr(self.acq_image, '_file_path_dict') and channel in self.acq_image._file_path_dict:
            return
        
        raise ValueError(
            f"Channel {channel} does not exist. "
            f"Available channels: {channel_keys if channel_keys else list(self.acq_image._file_path_dict.keys()) if hasattr(self.acq_image, '_file_path_dict') else 'none'}"
        )

    def create_roi(
        self,
        left: int,
        top: int,
        right: int,
        bottom: int,
        channel: int = 1,
        z: int = 0,
        name: str = "",
        note: str = "",
    ) -> ROI:
        """Create a new ROI, assign a unique id, and store it in the set.

        Validates channel exists and z coordinate is valid. Clamps coordinates
        to current image bounds.

        Args:
            left: Left coordinate in full-image pixels.
            top: Top coordinate in full-image pixels.
            right: Right coordinate in full-image pixels.
            bottom: Bottom coordinate in full-image pixels.
            channel: Channel number (defaults to 1).
            z: Image plane/slice number (defaults to 0). For 2D images, must be 0.
            name: Optional human-readable name.
            note: Optional free-form note.

        Returns:
            The newly created ROI instance.

        Raises:
            ValueError: If channel doesn't exist or z coordinate is invalid.
        """
        # Validate channel exists
        self._validate_channel(channel)
        
        # Get bounds for validation
        img_w, img_h, num_slices = self._get_bounds()
        
        # Clamp z to valid range [0, num_slices-1]
        if z < 0:
            logger.warning(f"z coordinate {z} is negative, clamping to 0")
            z = 0
        elif z >= num_slices:
            logger.warning(f"z coordinate {z} exceeds num_slices {num_slices}, clamping to {num_slices-1}")
            z = num_slices - 1
        
        # Clamp coordinates to image bounds
        left, top, right, bottom = clamp_coordinates_to_size(
            left, top, right, bottom, img_w, img_h
        )
        
        roi = ROI(
            id=self._next_id,
            channel=channel,
            z=z,
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

    def edit_roi(
        self,
        roi_id: int,
        *,
        left: int | None = None,
        top: int | None = None,
        right: int | None = None,
        bottom: int | None = None,
        channel: int | None = None,
        z: int | None = None,
        name: str | None = None,
        note: str | None = None,
    ) -> None:
        """Edit ROI coordinates or attributes.

        Validates channel and z if changed. Clamps coordinates to current image bounds.

        Args:
            roi_id: Identifier of the ROI to edit.
            left: New left coordinate (optional).
            top: New top coordinate (optional).
            right: New right coordinate (optional).
            bottom: New bottom coordinate (optional).
            channel: New channel number (optional).
            z: New z (plane) coordinate (optional).
            name: New name (optional).
            note: New note (optional).

        Raises:
            ValueError: If ROI not found, channel doesn't exist, or z coordinate is invalid.
        """
        if roi_id not in self._rois:
            raise ValueError(f"ROI {roi_id} not found")
        
        roi = self._rois[roi_id]
        old_geom = (roi.left, roi.top, roi.right, roi.bottom, roi.channel, roi.z)

        old_geom = (roi.left, roi.top, roi.right, roi.bottom, roi.channel, roi.z)
        
        # Update channel if provided
        if channel is not None:
            self._validate_channel(channel)
            roi.channel = channel
        
        # Get bounds for validation
        img_w, img_h, num_slices = self._get_bounds()
        
        # Validate and clamp z coordinate if provided
        if z is not None:
            # Clamp z to valid range [0, num_slices-1]
            if z < 0:
                logger.warning(f"z coordinate {z} is negative, clamping to 0")
                z = 0
            elif z >= num_slices:
                logger.warning(f"z coordinate {z} exceeds num_slices {num_slices}, clamping to {num_slices-1}")
                z = num_slices - 1
            roi.z = z
        
        # Update coordinates if provided
        new_left = left if left is not None else roi.left
        new_top = top if top is not None else roi.top
        new_right = right if right is not None else roi.right
        new_bottom = bottom if bottom is not None else roi.bottom
        
        # Clamp coordinates to image bounds
        clamped_left, clamped_top, clamped_right, clamped_bottom = clamp_coordinates_to_size(
            new_left, new_top, new_right, new_bottom, img_w, img_h
        )
        
        roi.left = clamped_left
        roi.top = clamped_top
        roi.right = clamped_right
        roi.bottom = clamped_bottom
        
        # Update name and note if provided
        if name is not None:
            roi.name = name
        if note is not None:
            roi.note = note

        new_geom = (roi.left, roi.top, roi.right, roi.bottom, roi.channel, roi.z)
        if new_geom != old_geom:
            roi.revision += 1
    
    def delete(self, roi_id: int) -> None:
        """Remove the ROI with the given id, if it exists.

        Args:
            roi_id: Identifier of the ROI to remove.
        """
        self._rois.pop(roi_id, None)

    def clear(self) -> int:
        """Delete all ROIs and reset internal id counter.

        Returns:
            Number of ROIs deleted.
        """
        n = len(self._rois)
        self._rois.clear()
        self._next_id = 1
        return n

    def get(self, roi_id: int) -> ROI | None:
        """Return the ROI with the given id, or None if not present.

        Args:
            roi_id: Identifier of the ROI to retrieve.

        Returns:
            The ROI instance or None.
        """
        return self._rois.get(roi_id)
    
    def get_roi_ids(self) -> list[int]:
        """Get all ROI IDs in creation order.
        
        Returns:
            List of ROI IDs (integers) in creation order.
        """
        return list(self._rois.keys())
    
    def numRois(self) -> int:
        """Return the number of ROIs in the set.
        
        Returns:
            Number of ROIs.
        """
        return len(self._rois)
    
    def revalidate_all(self) -> int:
        """Revalidate and clamp all ROIs to current image bounds.

        This is an optional utility method. Bounds validation normally happens
        automatically in create_roi(), edit_roi(), and during load_metadata().

        Returns:
            Number of ROIs that were clamped (modified).
        """
        clamped_count = 0
        
        for roi in self._rois.values():
            try:
                img_w, img_h, num_slices = self._get_bounds()
                
                # Validate and clamp z
                original_z = roi.z
                if roi.z < 0:
                    roi.z = 0
                    clamped_count += 1
                elif roi.z >= num_slices:
                    roi.z = num_slices - 1
                    clamped_count += 1
                
                # Clamp coordinates
                clamped_left, clamped_top, clamped_right, clamped_bottom = clamp_coordinates_to_size(
                    roi.left, roi.top, roi.right, roi.bottom, img_w, img_h
                )
                
                if (roi.left != clamped_left or roi.top != clamped_top or
                    roi.right != clamped_right or roi.bottom != clamped_bottom or
                    roi.z != original_z):
                    roi.left = clamped_left
                    roi.top = clamped_top
                    roi.right = clamped_right
                    roi.bottom = clamped_bottom
                    clamped_count += 1
                    
            except ValueError as e:
                logger.warning(f"Could not revalidate ROI {roi.id}: {e}")
        
        return clamped_count

    def __iter__(self) -> Iterable[ROI]:
        """Iterate over ROIs in creation order."""
        return iter(self._rois.values())

    def as_list(self) -> list[ROI]:
        """Return all ROIs as a list in creation order.
        
        Returns:
            List of ROI instances in creation order.
        """
        return list(self._rois.values())

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize all ROIs to a list of dictionaries for JSON storage.

        Returns:
            A list of dictionaries, each compatible with `ROI.from_dict`.
        """
        return [roi.to_dict() for roi in self._rois.values()]

    @classmethod
    def from_list(cls, data: list[dict[str, Any]], acq_image: "AcqImage") -> "RoiSet":
        """Create a ROI set from a list of ROI dictionaries.

        Args:
            data: List of dictionaries, each produced by `ROI.to_dict`.
            acq_image: Reference to AcqImage instance for bounds validation.

        Returns:
            A new RoiSet containing all deserialized ROIs.
        """
        s = cls(acq_image)
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
    for roi in reversed(rois.as_list()):
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

