# kymflow/core/image_loaders/roi.py

from __future__ import annotations

from dataclasses import dataclass, asdict, field
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
class RoiBounds:
    """Axis-aligned rectangular bounds in pixel coordinates.
    
    Represents the bounds of an ROI using explicit dimension indices.
    For a 2D image with shape (H, W):
    - dim0_start/dim0_stop: start/stop indices in dimension 0 (rows/height)
    - dim1_start/dim1_stop: start/stop indices in dimension 1 (columns/width)
    
    This is the atomic unit for all coordinate operations in the ROI API.
    """
    dim0_start: int
    dim0_stop: int
    dim1_start: int
    dim1_stop: int
    
    @classmethod
    def from_image_bounds(cls, image_bounds: "ImageBounds") -> "RoiBounds":
        """Create RoiBounds that encompasses the entire image.
        
        Args:
            image_bounds: ImageBounds with width, height, and num_slices.
            
        Returns:
            RoiBounds covering the full image (dim0: 0 to height, dim1: 0 to width).
        """
        return cls(
            dim0_start=0,
            dim0_stop=image_bounds.height,
            dim1_start=0,
            dim1_stop=image_bounds.width,
        )
    
    @classmethod
    def from_image_size(cls, size: "ImageSize") -> "RoiBounds":
        """Create RoiBounds that encompasses the entire image.
        
        Args:
            size: ImageSize with width and height dimensions.
            
        Returns:
            RoiBounds covering the full image (dim0: 0 to height, dim1: 0 to width).
        """
        return cls(
            dim0_start=0,
            dim0_stop=size.height,
            dim1_start=0,
            dim1_stop=size.width,
        )

@dataclass
class RoiBoundsFloat:
    """Axis-aligned rectangular bounds in physical units (float coordinates).
    
    Similar to RoiBounds but with float values for physical coordinate conversions.
    """
    dim0_start: float
    dim0_stop: float
    dim1_start: float
    dim1_stop: float

@dataclass
class ImageBounds:
    """Image bounds including 2D dimensions and 3D slice information.
    
    Used for full image metadata including 3D structure.
    For 2D images: num_slices = 1
    For 3D images: num_slices = number of slices
    
    Fields:
        width: Width of image in pixels (dimension 1, columns)
        height: Height of image in pixels (dimension 0, rows)
        num_slices: Number of slices/planes (1 for 2D images)
    """
    width: int      # dim1 (columns)
    height: int     # dim0 (rows)
    num_slices: int

@dataclass
class ImageSize:
    """2D image dimensions for coordinate clamping operations.
    
    Used for 2D coordinate clamping (doesn't include 3D slice info).
    
    Fields:
        width: Width of image in pixels (dimension 1, columns)
        height: Height of image in pixels (dimension 0, rows)
    """
    width: int      # dim1 (columns)
    height: int     # dim0 (rows)

@dataclass
class ROI:
    """Axis-aligned rectangular ROI in full-image pixel coordinates.

    Coordinates are expressed in the coordinate system of the full image
    (not the zoomed view). By convention:

    * bounds.dim0_start <= bounds.dim0_stop
    * bounds.dim1_start <= bounds.dim1_stop

    These invariants are enforced by `clamp_to_image` (or `clamp_to_bounds`).
    
    For a 2D image with shape (H, W):
    - bounds.dim0_start/dim0_stop: start/stop indices in dimension 0 (rows/height)
    - bounds.dim1_start/dim1_stop: start/stop indices in dimension 1 (columns/width)
    
    Each ROI is associated with a specific channel and z (plane/slice) coordinate.
    For 2D images, z is always 0. For 3D images, z is in [0, num_slices-1].
    """

    id: int
    channel: int = 1
    z: int = 0
    name: str = ""
    note: str = ""
    bounds: RoiBounds = field(default_factory=lambda: RoiBounds(dim0_start=0, dim0_stop=0, dim1_start=0, dim1_stop=0))
    # Increments when ROI geometry (or channel/z) changes. Used to mark analysis as stale.
    revision: int = 0

    def clamp_to_image(self, img: np.ndarray) -> None:
        """Clamp ROI to be fully inside the given image.

        This ensures that:
        * all coordinates are within [0, img.shape[0]] × [0, img.shape[1]]
        * bounds.dim0_start <= bounds.dim0_stop and bounds.dim1_start <= bounds.dim1_stop (by swapping coordinates if needed)

        Args:
            img: 2D numpy array.
        """
        self.bounds = clamp_coordinates(self.bounds, img)

    def clamp_to_bounds(self, size: "ImageSize") -> None:
        """Clamp ROI to [0, size.height] × [0, size.width] and fix inverted edges.

        Args:
            size: ImageSize with width and height dimensions.
        """
        self.bounds = clamp_coordinates_to_size(self.bounds, size)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation of this ROI."""
        result = asdict(self)
        # Flatten bounds for JSON serialization (convert RoiBounds to dict)
        bounds_dict = result.pop('bounds')
        result.update(bounds_dict)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ROI":
        """Create a ROI from a dictionary produced by to_dict().

        Args:
            data: Dictionary with flattened bounds fields (dim0_start, dim0_stop, etc.).
                Float coordinates will be converted to int.
                Missing channel/z will default to 1/0.

        Returns:
            A new ROI instance initialized from the dictionary.
        """
        # Work on a copy so we don't mutate the caller's dict.
        data = dict(data)

        # Extract flattened bounds fields
        bounds = RoiBounds(
            dim0_start=int(data.pop('dim0_start', 0)),
            dim0_stop=int(data.pop('dim0_stop', 0)),
            dim1_start=int(data.pop('dim1_start', 0)),
            dim1_stop=int(data.pop('dim1_stop', 0)),
        )
        
        # Convert float channel/z to int if present
        for field_name in ['channel', 'z']:
            if field_name in data and isinstance(data[field_name], float):
                data[field_name] = int(data[field_name])
        
        # Default channel=1, z=0 if not present
        if 'channel' not in data:
            data['channel'] = 1
        if 'z' not in data:
            data['z'] = 0

        # Default revision to 0 if not present
        if 'revision' not in data:
            data['revision'] = 0
        
        data['bounds'] = bounds
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
    
    def _get_image_bounds(self) -> "ImageBounds":
        """Get image bounds from AcqImage.
        
        Delegates to AcqImage.get_image_bounds() for consistency.
        
        Returns:
            ImageBounds with width, height, and num_slices.
            
        Raises:
            ValueError: If bounds cannot be determined.
        """
        return self.acq_image.get_image_bounds()
    
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
        
        raise ValueError(
            f"Channel {channel} does not exist. "
            f"Available channels: {channel_keys if channel_keys else 'none'}"
        )

    def create_roi(
        self,
        bounds: RoiBounds | None = None,
        channel: int = 1,
        z: int = 0,
        name: str = "",
        note: str = "",
    ) -> ROI:
        """Create a new ROI, assign a unique id, and store it in the set.

        Validates channel exists and z coordinate is valid. Clamps coordinates
        to current image bounds. If bounds is None, creates an ROI that encompasses
        the entire image.

        Args:
            bounds: RoiBounds defining the ROI coordinates. If None, creates bounds
                that encompass the entire image.
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
        image_bounds = self._get_image_bounds()
        
        # If bounds is None, create full-image bounds
        if bounds is None:
            bounds = RoiBounds.from_image_bounds(image_bounds)
        
        # Clamp z to valid range [0, num_slices-1]
        if z < 0:
            logger.warning(f"z coordinate {z} is negative, clamping to 0")
            z = 0
        elif z >= image_bounds.num_slices:
            logger.warning(f"z coordinate {z} exceeds num_slices {image_bounds.num_slices}, clamping to {image_bounds.num_slices-1}")
            z = image_bounds.num_slices - 1
        
        # Clamp coordinates to image bounds
        size = ImageSize(width=image_bounds.width, height=image_bounds.height)
        clamped_bounds = clamp_coordinates_to_size(bounds, size)
        
        roi = ROI(
            id=self._next_id,
            channel=channel,
            z=z,
            name=name,
            note=note,
            bounds=clamped_bounds,
        )
        self._rois[roi.id] = roi
        self._next_id += 1
        self.acq_image.mark_metadata_dirty()
        return roi

    def edit_roi(
        self,
        roi_id: int,
        *,
        bounds: RoiBounds | None = None,
        channel: int | None = None,
        z: int | None = None,
        name: str | None = None,
        note: str | None = None,
    ) -> None:
        """Edit ROI coordinates or attributes.

        Validates channel and z if changed. Clamps coordinates to current image bounds.

        Args:
            roi_id: Identifier of the ROI to edit.
            bounds: New RoiBounds (optional). If None, coordinates are unchanged.
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
        old_bounds = roi.bounds
        old_geom = (old_bounds.dim0_start, old_bounds.dim0_stop, old_bounds.dim1_start, old_bounds.dim1_stop, roi.channel, roi.z)
        
        # Update channel if provided
        changed = False
        if channel is not None:
            self._validate_channel(channel)
            if roi.channel != channel:
                roi.channel = channel
                changed = True
        
        # Get bounds for validation
        image_bounds = self._get_image_bounds()
        
        # Validate and clamp z coordinate if provided
        if z is not None:
            # Clamp z to valid range [0, num_slices-1]
            if z < 0:
                logger.warning(f"z coordinate {z} is negative, clamping to 0")
                z = 0
            elif z >= image_bounds.num_slices:
                logger.warning(f"z coordinate {z} exceeds num_slices {image_bounds.num_slices}, clamping to {image_bounds.num_slices-1}")
                z = image_bounds.num_slices - 1
            if roi.z != z:
                roi.z = z
                changed = True
        
        # Update coordinates if provided
        if bounds is not None:
            # Clamp coordinates to image bounds
            size = ImageSize(width=image_bounds.width, height=image_bounds.height)
            clamped_bounds = clamp_coordinates_to_size(bounds, size)
            if roi.bounds != clamped_bounds:
                roi.bounds = clamped_bounds
                changed = True
        
        # Update name and note if provided
        if name is not None and roi.name != name:
            roi.name = name
            changed = True
        if note is not None and roi.note != note:
            roi.note = note
            changed = True

        new_geom = (roi.bounds.dim0_start, roi.bounds.dim0_stop, roi.bounds.dim1_start, roi.bounds.dim1_stop, roi.channel, roi.z)
        if new_geom != old_geom:
            roi.revision += 1
            changed = True
        if changed:
            self.acq_image.mark_metadata_dirty()
    
    def delete(self, roi_id: int) -> None:
        """Remove the ROI with the given id, if it exists.

        Args:
            roi_id: Identifier of the ROI to remove.
        """
        removed = self._rois.pop(roi_id, None)
        if removed is not None:
            self.acq_image.mark_metadata_dirty()

    def clear(self) -> int:
        """Delete all ROIs and reset internal id counter.

        Returns:
            Number of ROIs deleted.
        """
        n = len(self._rois)
        self._rois.clear()
        self._next_id = 1
        if n > 0:
            self.acq_image.mark_metadata_dirty()
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
                image_bounds = self._get_image_bounds()
                
                # Validate and clamp z
                original_z = roi.z
                if roi.z < 0:
                    roi.z = 0
                    clamped_count += 1
                elif roi.z >= image_bounds.num_slices:
                    roi.z = image_bounds.num_slices - 1
                    clamped_count += 1
                
                # Clamp coordinates
                size = ImageSize(width=image_bounds.width, height=image_bounds.height)
                clamped_bounds = clamp_coordinates_to_size(roi.bounds, size)
                
                if (roi.bounds.dim0_start != clamped_bounds.dim0_start or
                    roi.bounds.dim0_stop != clamped_bounds.dim0_stop or
                    roi.bounds.dim1_start != clamped_bounds.dim1_start or
                    roi.bounds.dim1_stop != clamped_bounds.dim1_stop or
                    roi.z != original_z):
                    roi.bounds = clamped_bounds
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
    bounds: RoiBounds,
    img: np.ndarray
) -> RoiBounds:
    """Clamp coordinates to be within bounds of img.shape (H, W).
    
    Args:
        bounds: RoiBounds to clamp.
        img: 2D numpy array (enforces 2D).
    
    Returns:
        Clamped RoiBounds.
    
    Raises:
        ValueError: If img is not 2D.
    """
    if img.ndim != 2:
        raise ValueError(f"Expected a 2D image, got ndim {img.ndim}")
    
    height, width = img.shape
    
    def clamp(v: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, v))
    
    dim1_start = clamp(bounds.dim1_start, 0, width)
    dim1_stop = clamp(bounds.dim1_stop, 0, width)
    dim0_start = clamp(bounds.dim0_start, 0, height)
    dim0_stop = clamp(bounds.dim0_stop, 0, height)
    
    # Ensure non-inverted coordinates
    if dim1_start > dim1_stop:
        dim1_start, dim1_stop = dim1_stop, dim1_start
    if dim0_start > dim0_stop:
        dim0_start, dim0_stop = dim0_stop, dim0_start
    
    return RoiBounds(
        dim0_start=dim0_start,
        dim0_stop=dim0_stop,
        dim1_start=dim1_start,
        dim1_stop=dim1_stop,
    )


def clamp_coordinates_to_size(
    bounds: RoiBounds,
    size: ImageSize
) -> RoiBounds:
    """Clamp coordinates to [0, size.width] × [0, size.height] and fix inverted edges.
    
    Helper function for cases where we only have width/height metadata
    (e.g., loading from JSON without image data).
    
    Args:
        bounds: RoiBounds to clamp.
        size: ImageSize with width and height dimensions.
    
    Returns:
        Clamped RoiBounds.
    """
    def clamp(v: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, v))
    
    dim1_start = clamp(bounds.dim1_start, 0, size.width)
    dim1_stop = clamp(bounds.dim1_stop, 0, size.width)
    dim0_start = clamp(bounds.dim0_start, 0, size.height)
    dim0_stop = clamp(bounds.dim0_stop, 0, size.height)
    
    # Ensure non-inverted coordinates
    if dim1_start > dim1_stop:
        dim1_start, dim1_stop = dim1_stop, dim1_start
    if dim0_start > dim0_stop:
        dim0_start, dim0_stop = dim0_stop, dim0_start
    
    return RoiBounds(
        dim0_start=dim0_start,
        dim0_stop=dim0_stop,
        dim1_start=dim1_start,
        dim1_stop=dim1_stop,
    )


def roi_rect_is_equal(bounds1: RoiBounds, bounds2: RoiBounds) -> bool:
    """Check if two RoiBounds have the same coordinates.
    
    Args:
        bounds1: First RoiBounds to compare.
        bounds2: Second RoiBounds to compare.
    
    Returns:
        True if coordinates are equal, False otherwise.
    """
    return (
        bounds1.dim0_start == bounds2.dim0_start
        and bounds1.dim0_stop == bounds2.dim0_stop
        and bounds1.dim1_start == bounds2.dim1_start
        and bounds1.dim1_stop == bounds2.dim1_stop
    )


def point_in_roi(bounds: RoiBounds, dim0_coord: int, dim1_coord: int) -> bool:
    """Return True if point (dim0_coord, dim1_coord) lies inside or on the boundary of bounds.

    Args:
        bounds: RoiBounds to test against.
        dim0_coord: Coordinate in dimension 0 (rows/height).
        dim1_coord: Coordinate in dimension 1 (columns/width).

    Returns:
        True if the point is inside the bounds or on its edges, False otherwise.
    """
    return (
        bounds.dim0_start <= dim0_coord <= bounds.dim0_stop
        and bounds.dim1_start <= dim1_coord <= bounds.dim1_stop
    )


def hit_test_rois(
    rois: RoiSet,
    dim0_coord: int,
    dim1_coord: int,
    edge_tol: int = 5,
) -> tuple[ROI | None, str | None]:
    """Hit-test a collection of ROIs at point (dim0_coord, dim1_coord) in full-image coordinates.

    This function checks the four edges of each ROI with a tolerance and then
    the interior area. It iterates over ROIs in reverse creation order
    so that "topmost" (most recently created) ROIs are hit first.

    Args:
        rois: Collection of ROIs to test.
        dim0_coord: Coordinate in dimension 0 (rows/height).
        dim1_coord: Coordinate in dimension 1 (columns/width).
        edge_tol: Tolerance in pixels to treat a point as "on an edge".

    Returns:
        A tuple (roi, mode) where:
            roi: The hit ROI instance, or None if nothing was hit.
            mode: One of:
                'resizing_dim1_start' (was 'resizing_left'),
                'resizing_dim1_stop' (was 'resizing_right'),
                'resizing_dim0_start' (was 'resizing_top'),
                'resizing_dim0_stop' (was 'resizing_bottom'),
                'moving',
                or None if no hit occurred.
    """
    # Reverse the creation order to hit "topmost" ROIs first.
    for roi in reversed(rois.as_list()):
        bounds = roi.bounds

        near_dim1_start = (
            abs(dim1_coord - bounds.dim1_start) <= edge_tol
            and bounds.dim0_start <= dim0_coord <= bounds.dim0_stop
        )
        near_dim1_stop = (
            abs(dim1_coord - bounds.dim1_stop) <= edge_tol
            and bounds.dim0_start <= dim0_coord <= bounds.dim0_stop
        )
        near_dim0_start = (
            abs(dim0_coord - bounds.dim0_start) <= edge_tol
            and bounds.dim1_start <= dim1_coord <= bounds.dim1_stop
        )
        near_dim0_stop = (
            abs(dim0_coord - bounds.dim0_stop) <= edge_tol
            and bounds.dim1_start <= dim1_coord <= bounds.dim1_stop
        )

        if near_dim1_start:
            return roi, "resizing_dim1_start"
        if near_dim1_stop:
            return roi, "resizing_dim1_stop"
        if near_dim0_start:
            return roi, "resizing_dim0_start"
        if near_dim0_stop:
            return roi, "resizing_dim0_stop"
        if point_in_roi(bounds, dim0_coord, dim1_coord):
            return roi, "moving"

    return None, None

