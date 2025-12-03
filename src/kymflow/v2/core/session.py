# kymflow/core/session.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
from PIL import Image

from kymflow.v2.core.image import KymImage, array_to_pil
from kymflow.v2.core.viewport import KymViewport
from kymflow.v2.core.roi import KymRoiSet, KymRoi


@dataclass
class KymSession:
    """Bundle of image, viewport, and ROI set for a single kym viewer.

    This is a lightweight container holding the core state required to
    manipulate and render a single kymograph: the underlying image, the
    current viewport, and all defined ROIs.
    """

    image: KymImage
    viewport: KymViewport
    rois: KymRoiSet


class KymEngine:
    """Backend engine for manipulating a kym image, viewport, and ROIs.

    This class provides a GUI-agnostic API that your frontend (NiceGUI,
    Plotly, PyQt, etc.) can call into. It does not depend on any particular
    UI framework; it only operates on numeric values and core dataclasses.

    Typical usage:

        engine = KymEngine(kym_array, display_size=(1000, 100))
        engine.zoom_reset()
        roi = engine.start_drawing_roi(x_full, y_full)
        engine.update_drawing_roi(roi.id, x_full2, y_full2)
        pil_img = engine.render_view_pil(vmin, vmax, cmap="gray")

    Attributes:
        session: KymSession holding image, viewport, and ROI set.
        display_size: (width, height) of the logical display resolution.
            This is the size you intend to render to (e.g. PNG size) and is
            used for coordinate transforms in the frontend, not enforced here.
    """

    def __init__(
        self,
        kym_array: np.ndarray,
        display_size: Tuple[int, int],
    ) -> None:
        """Initialize the engine from a raw NumPy array and a display size.

        Args:
            kym_array: 2D NumPy array containing the kym image.
            display_size: (display_width, display_height) in pixels, describing
                how large the rendered view should be. This does not resample
                the data by itself; it is used by the frontend to interpret
                display coordinates.
        """
        image = KymImage(kym_array)
        viewport = KymViewport(img_width=image.width, img_height=image.height)
        rois = KymRoiSet()

        self.session = KymSession(image=image, viewport=viewport, rois=rois)
        self.display_width, self.display_height = display_size

    # ------------------------------------------------------------------
    # Properties for convenience
    # ------------------------------------------------------------------

    @property
    def image(self) -> KymImage:
        """Return the underlying KymImage."""
        return self.session.image

    @property
    def viewport(self) -> KymViewport:
        """Return the current viewport."""
        return self.session.viewport

    @property
    def rois(self) -> KymRoiSet:
        """Return the ROI set."""
        return self.session.rois

    # ------------------------------------------------------------------
    # Viewport operations
    # ------------------------------------------------------------------

    def zoom_reset(self) -> None:
        """Reset the viewport to show the full image."""
        self.viewport.reset()

    def zoom_around(
        self,
        x_full: float,
        y_full: float,
        factor_x: float,
        factor_y: float,
        min_width: float = 10.0,
        min_height: float = 5.0,
    ) -> None:
        """Zoom the viewport around a given point.

        Args:
            x_full: X coordinate in full-image pixels to zoom around.
            y_full: Y coordinate in full-image pixels to zoom around.
            factor_x: Zoom factor along X (<1 zoom in, >1 zoom out).
            factor_y: Zoom factor along Y (<1 zoom in, >1 zoom out).
            min_width: Minimum allowed viewport width.
            min_height: Minimum allowed viewport height.
        """
        self.viewport.zoom_around(
            x_center=x_full,
            y_center=y_full,
            factor_x=factor_x,
            factor_y=factor_y,
            min_width=min_width,
            min_height=min_height,
        )

    def pan(self, dx_full: float, dy_full: float) -> None:
        """Pan the viewport by the given deltas in full-image coordinates.

        Args:
            dx_full: Delta X in full-image pixels.
            dy_full: Delta Y in full-image pixels.
        """
        self.viewport.pan(dx=dx_full, dy=dy_full)

    def get_view_slice(self) -> Tuple[int, int, int, int]:
        """Return integer indices representing the current view region.

        Returns:
            (y_min, y_max, x_min, x_max) suitable for NumPy slicing:
                sub = image.data[y_min:y_max, x_min:x_max]
        """
        return self.viewport.get_int_slice()

    # ------------------------------------------------------------------
    # ROI operations
    # ------------------------------------------------------------------

    def start_drawing_roi(self, x_full: float, y_full: float) -> KymRoi:
        """Begin a new ROI at the given full-image coordinates.

        Args:
            x_full: X coordinate in full-image pixels where drawing starts.
            y_full: Y coordinate in full-image pixels where drawing starts.

        Returns:
            The newly created ROI with left=right=x_full and top=bottom=y_full.
        """
        roi = self.rois.create_roi(
            left=x_full,
            top=y_full,
            right=x_full,
            bottom=y_full,
        )
        roi.clamp_to_image(self.image)
        return roi

    def update_drawing_roi(
        self,
        roi_id: int,
        x_full: float,
        y_full: float,
        x_start: float,
        y_start: float,
    ) -> None:
        """Update an ROI during drawing (rubber-band rectangle).

        Args:
            roi_id: Identifier of the ROI being drawn.
            x_full: Current X coordinate in full-image pixels.
            y_full: Current Y coordinate in full-image pixels.
            x_start: Starting X coordinate of the drawing gesture.
            y_start: Starting Y coordinate of the drawing gesture.
        """
        roi = self.rois.get(roi_id)
        if roi is None:
            return
        roi.left = min(x_start, x_full)
        roi.top = min(y_start, y_full)
        roi.right = max(x_start, x_full)
        roi.bottom = max(y_start, y_full)
        roi.clamp_to_image(self.image)

    def move_roi(
        self,
        roi_id: int,
        dx_full: float,
        dy_full: float,
    ) -> None:
        """Move an ROI by a given offset in full-image coordinates.

        Args:
            roi_id: Identifier of the ROI to move.
            dx_full: Delta X in full-image pixels.
            dy_full: Delta Y in full-image pixels.
        """
        roi = self.rois.get(roi_id)
        if roi is None:
            return
        roi.left += dx_full
        roi.right += dx_full
        roi.top += dy_full
        roi.bottom += dy_full
        roi.clamp_to_image(self.image)

    def resize_roi_edge(
        self,
        roi_id: int,
        edge: str,
        x_full: float,
        y_full: float,
    ) -> None:
        """Resize an ROI by dragging one of its edges.

        Args:
            roi_id: Identifier of the ROI to resize.
            edge: One of 'left', 'right', 'top', 'bottom'.
            x_full: Current X coordinate in full-image pixels.
            y_full: Current Y coordinate in full-image pixels.
        """
        roi = self.rois.get(roi_id)
        if roi is None:
            return

        if edge == "left":
            roi.left = x_full
        elif edge == "right":
            roi.right = x_full
        elif edge == "top":
            roi.top = y_full
        elif edge == "bottom":
            roi.bottom = y_full
        else:
            raise ValueError(f"Unknown edge specifier: {edge!r}")

        roi.clamp_to_image(self.image)

    def delete_roi(self, roi_id: int) -> None:
        """Delete an ROI by its id."""
        self.rois.delete(roi_id)

    def set_roi_note(self, roi_id: int, note: str) -> None:
        """Set the free-form note associated with an ROI."""
        roi = self.rois.get(roi_id)
        if roi is not None:
            roi.note = note

    def set_roi_name(self, roi_id: int, name: str) -> None:
        """Set the human-readable name associated with an ROI."""
        roi = self.rois.get(roi_id)
        if roi is not None:
            roi.name = name

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def view_array(self) -> np.ndarray:
        """Return the current viewport region as a NumPy array."""
        return self.image.viewport_view(self.viewport)

    def render_view_pil(
        self,
        vmin: float | None = None,
        vmax: float | None = None,
        cmap: str = "gray",
        resize_to_display: bool = False,
    ) -> Image.Image:
        """Render the current viewport region as a PIL image.

        Args:
            vmin: Lower intensity bound used for normalization. If None, the
                minimum of the viewport data is used.
            vmax: Upper intensity bound used for normalization. If None, the
                maximum of the viewport data is used.
            cmap: Name of a Matplotlib colormap to use for RGB conversion.
            resize_to_display: If True, the resulting PIL image is resized to
                (display_width, display_height) using bilinear interpolation.

        Returns:
            A PIL Image with mode "RGB" representing the current view.
        """
        sub = self.view_array()
        img = array_to_pil(sub, vmin=vmin, vmax=vmax, cmap=cmap)
        if resize_to_display:
            img = img.resize(
                (self.display_width, self.display_height),
                Image.BILINEAR,
            )
        return img
