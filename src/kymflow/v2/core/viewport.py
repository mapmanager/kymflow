# kymflow/core/viewport.py

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Tuple


@dataclass
class KymViewport:
    """Viewport describing the currently visible region of a kym image.

    The viewport is defined in full-image pixel coordinates and is responsible
    for tracking zoom and pan state. It does not know about any particular GUI
    framework; it only deals with numeric coordinate ranges.

    Attributes:
        img_width:  Width of the underlying image in pixels.
        img_height: Height of the underlying image in pixels.
        x_min:      Left edge of the visible region in full-image pixels.
        x_max:      Right edge of the visible region in full-image pixels.
        y_min:      Top edge of the visible region in full-image pixels.
        y_max:      Bottom edge of the visible region in full-image pixels.
    """

    img_width: int
    img_height: int
    x_min: float = 0.0
    x_max: float = 0.0
    y_min: float = 0.0
    y_max: float = 0.0

    def __post_init__(self) -> None:
        """Initialize or validate the viewport.

        If x_max and y_max are zero (the default), the viewport is reset to
        show the full image. Otherwise, coordinates are clamped to the image
        bounds and minimal sanity checks are performed.
        """
        if self.x_max == 0.0 and self.y_max == 0.0:
            self.reset()
        else:
            self._clamp_to_image()

    # ------------------------------------------------------------------
    # Basic properties and serialization
    # ------------------------------------------------------------------

    @property
    def width(self) -> float:
        """Current viewport width in full-image pixels."""
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        """Current viewport height in full-image pixels."""
        return self.y_max - self.y_min

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of this viewport."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KymViewport":
        """Create a viewport from a dictionary produced by to_dict()."""
        return cls(**data)

    # ------------------------------------------------------------------
    # Core operations: reset, zoom, pan
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset the viewport to show the full image extent."""
        self.x_min = 0.0
        self.x_max = float(self.img_width)
        self.y_min = 0.0
        self.y_max = float(self.img_height)

    def zoom_around(
        self,
        x_center: float,
        y_center: float,
        factor_x: float,
        factor_y: float,
        min_width: float = 10.0,
        min_height: float = 5.0,
    ) -> None:
        """Zoom the viewport around a given point.

        Args:
            x_center:  X coordinate in full-image pixels to zoom around.
            y_center:  Y coordinate in full-image pixels to zoom around.
            factor_x:  Zoom factor along X. Values < 1 zoom in, > 1 zoom out.
            factor_y:  Zoom factor along Y. Values < 1 zoom in, > 1 zoom out.
            min_width: Minimum allowed viewport width in pixels.
            min_height: Minimum allowed viewport height in pixels.

        Notes:
            After applying the zoom, the viewport is clamped to image bounds
            and the width/height are enforced to be at least min_width /
            min_height.
        """
        # X axis zoom
        left_offset = self.x_min - x_center
        right_offset = self.x_max - x_center
        new_x_min = x_center + left_offset * factor_x
        new_x_max = x_center + right_offset * factor_x

        # Y axis zoom
        top_offset = self.y_min - y_center
        bottom_offset = self.y_max - y_center
        new_y_min = y_center + top_offset * factor_y
        new_y_max = y_center + bottom_offset * factor_y

        # Assign and clamp
        self.x_min, self.x_max = new_x_min, new_x_max
        self.y_min, self.y_max = new_y_min, new_y_max
        self._clamp_to_image()

        # Enforce minimum size
        self._ensure_min_size(min_width, min_height)
        self._clamp_to_image()

    def pan(self, dx: float, dy: float) -> None:
        """Pan the viewport by the given deltas in full-image coordinates.

        Args:
            dx: Delta in X (positive moves the visible window right).
            dy: Delta in Y (positive moves the visible window down).

        Notes:
            Panning is clamped so the viewport never leaves the image bounds.
        """
        self.x_min -= dx
        self.x_max -= dx
        self.y_min -= dy
        self.y_max -= dy
        self._clamp_to_image()

    def get_int_slice(self) -> Tuple[int, int, int, int]:
        """Return integer indices for slicing a NumPy array.

        Returns:
            (y_min, y_max, x_min, x_max) as integers suitable for NumPy
            slicing, e.g. `sub = kym[y_min:y_max, x_min:x_max]`.
        """
        y_min = max(0, min(self.img_height, int(round(self.y_min))))
        y_max = max(0, min(self.img_height, int(round(self.y_max))))
        x_min = max(0, min(self.img_width, int(round(self.x_min))))
        x_max = max(0, min(self.img_width, int(round(self.x_max))))
        return y_min, y_max, x_min, x_max

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clamp_to_image(self) -> None:
        """Clamp viewport edges to remain within the image bounds."""
        self.x_min = max(0.0, min(float(self.img_width), self.x_min))
        self.x_max = max(0.0, min(float(self.img_width), self.x_max))
        self.y_min = max(0.0, min(float(self.img_height), self.y_min))
        self.y_max = max(0.0, min(float(self.img_height), self.y_max))

        # If somehow inverted, reset to full image as a safe fallback.
        if self.x_max <= self.x_min:
            self.x_min = 0.0
            self.x_max = float(self.img_width)
        if self.y_max <= self.y_min:
            self.y_min = 0.0
            self.y_max = float(self.img_height)

    def _ensure_min_size(self, min_width: float, min_height: float) -> None:
        """Ensure the viewport is at least min_width × min_height in size."""
        # X dimension
        if self.width < min_width:
            cx = 0.5 * (self.x_min + self.x_max)
            half_w = min_width / 2.0
            self.x_min = cx - half_w
            self.x_max = cx + half_w

        # Y dimension
        if self.height < min_height:
            cy = 0.5 * (self.y_min + self.y_max)
            half_h = min_height / 2.0
            self.y_min = cy - half_h
            self.y_max = cy + half_h


# ----------------------------------------------------------------------
# Coordinate transforms between full-image space and display space
# ----------------------------------------------------------------------


def full_to_view(
    x: float,
    y: float,
    viewport: KymViewport,
    disp_w: int,
    disp_h: int,
) -> tuple[float, float]:
    """Convert full-image coordinates to view (display) coordinates.

    Args:
        x: X coordinate in full-image pixels (0 .. img_width).
        y: Y coordinate in full-image pixels (0 .. img_height).
        viewport: Current zoom window in full-image coordinates.
        disp_w: Width of the displayed image in pixels (e.g. PNG width).
        disp_h: Height of the displayed image in pixels (e.g. PNG height).

    Returns:
        (vx, vy): Coordinates in view/display space (0 .. disp_w, 0 .. disp_h),
        suitable for drawing overlays (e.g. SVG rectangles) on top of the
        rendered image.
    """
    Wv = viewport.width
    Hv = viewport.height
    if Wv <= 0 or Hv <= 0:
        return 0.0, 0.0

    vx = (x - viewport.x_min) / Wv * disp_w
    vy = (y - viewport.y_min) / Hv * disp_h
    return vx, vy


def view_to_full(
    vx: float,
    vy: float,
    viewport: KymViewport,
    disp_w: int,
    disp_h: int,
) -> tuple[float, float]:
    """Convert view (display) coordinates back to full-image coordinates.

    Args:
        vx: X coordinate in display pixels (0 .. disp_w).
        vy: Y coordinate in display pixels (0 .. disp_h).
        viewport: Current zoom window in full-image coordinates.
        disp_w: Width of the displayed image in pixels.
        disp_h: Height of the displayed image in pixels.

    Returns:
        (x, y): Coordinates in full-image pixel space (0 .. img_width,
        0 .. img_height), suitable for ROI geometry or indexing into the kym
        array.
    """
    Wv = viewport.width
    Hv = viewport.height
    if Wv <= 0 or Hv <= 0:
        return viewport.x_min, viewport.y_min

    x = viewport.x_min + (vx / disp_w) * Wv
    y = viewport.y_min + (vy / disp_h) * Hv
    return x, y
