# kymflow/core/image.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
from PIL import Image
import matplotlib.cm as cm

from kymflow.v2.core.viewport import KymViewport


@dataclass
class KymImage:
    """Simple wrapper around a 2D kymograph image.

    This class encapsulates the underlying NumPy array and exposes width/height
    via a small, stable API. In the future it can be extended to handle loading
    from disk (TIFF, etc.) and basic metadata.

    Attributes:
        data: 2D NumPy array of shape (height, width) representing the kym image.
    """

    data: np.ndarray

    def __post_init__(self) -> None:
        """Validate that the underlying array is 2D."""
        if self.data.ndim != 2:
            raise ValueError(
                f"KymImage expects a 2D array, got shape {self.data.shape!r}"
            )

    @property
    def width(self) -> int:
        """Return the image width in pixels (X dimension)."""
        return int(self.data.shape[1])

    @property
    def height(self) -> int:
        """Return the image height in pixels (Y dimension)."""
        return int(self.data.shape[0])

    @property
    def shape(self) -> Tuple[int, int]:
        """Return the (height, width) shape of the image."""
        return int(self.data.shape[0]), int(self.data.shape[1])

    # ------------------------------------------------------------------
    # Data access helpers
    # ------------------------------------------------------------------

    def full_view(self) -> np.ndarray:
        """Return a view of the full kym image as a NumPy array.

        Returns:
            A 2D NumPy array of shape (height, width).
        """
        return self.data

    def viewport_view(self, viewport: KymViewport) -> np.ndarray:
        """Return a cropped view of the image according to a viewport.

        Args:
            viewport: KymViewport describing the visible region.

        Returns:
            A 2D NumPy array slice corresponding to the viewport.
        """
        y_min, y_max, x_min, x_max = viewport.get_int_slice()
        return self.data[y_min:y_max, x_min:x_max]

    # ------------------------------------------------------------------
    # Intensity scaling helpers
    # ------------------------------------------------------------------

    def compute_percentile_limits(
        self,
        low_percent: float,
        high_percent: float,
    ) -> Tuple[float, float]:
        """Compute intensity limits based on percentiles.

        Args:
            low_percent: Lower percentile in [0, 100], e.g. 5 for 5th percentile.
            high_percent: Upper percentile in [0, 100], e.g. 95 for 95th percentile.

        Returns:
            (vmin, vmax) intensity values computed from the full image.
        """
        if not (0.0 <= low_percent <= 100.0 and 0.0 <= high_percent <= 100.0):
            raise ValueError("Percentiles must be in [0, 100].")
        if high_percent <= low_percent:
            raise ValueError("high_percent must be greater than low_percent.")

        flat = self.data.ravel()
        vmin = float(np.nanpercentile(flat, low_percent))
        vmax = float(np.nanpercentile(flat, high_percent))
        if vmax <= vmin:
            vmax = vmin + 1e-6
        return vmin, vmax

    # ------------------------------------------------------------------
    # Conversions to PIL images
    # ------------------------------------------------------------------

    def to_pil(
        self,
        vmin: float | None = None,
        vmax: float | None = None,
        cmap: str = "gray",
    ) -> Image.Image:
        """Convert the full kym image to a 3-channel PIL image.

        Args:
            vmin: Lower intensity bound used for normalization. If None, the
                minimum of the data is used.
            vmax: Upper intensity bound used for normalization. If None, the
                maximum of the data is used.
            cmap: Name of a Matplotlib colormap to use for RGB conversion.

        Returns:
            A PIL Image with mode "RGB".
        """
        return array_to_pil(self.data, vmin=vmin, vmax=vmax, cmap=cmap)

    def viewport_to_pil(
        self,
        viewport: KymViewport,
        vmin: float | None = None,
        vmax: float | None = None,
        cmap: str = "gray",
    ) -> Image.Image:
        """Convert the current viewport region to a 3-channel PIL image.

        Args:
            viewport: KymViewport describing the visible region.
            vmin: Lower intensity bound used for normalization. If None, the
                minimum of the cropped data is used.
            vmax: Upper intensity bound used for normalization. If None, the
                maximum of the cropped data is used.
            cmap: Name of a Matplotlib colormap to use for RGB conversion.

        Returns:
            A PIL Image with mode "RGB" representing only the viewport region.
        """
        sub = self.viewport_view(viewport)
        return array_to_pil(sub, vmin=vmin, vmax=vmax, cmap=cmap)


def array_to_pil(
    arr: np.ndarray,
    vmin: float | None = None,
    vmax: float | None = None,
    cmap: str = "gray",
) -> Image.Image:
    """Map a 2D NumPy array to an 8-bit RGB PIL image with a colormap.

    This function is backend-only and does not depend on any GUI framework.

    Args:
        arr: 2D NumPy array of image intensities.
        vmin: Lower intensity bound used for normalization. If None, the
            minimum of the data is used.
        vmax: Upper intensity bound used for normalization. If None, the
            maximum of the data is used.
        cmap: Name of a Matplotlib colormap to use for RGB conversion.

    Returns:
        A PIL Image with mode "RGB".
    """
    arr = np.asarray(arr, dtype=float)

    if vmin is None:
        vmin = float(np.nanmin(arr))
    if vmax is None:
        vmax = float(np.nanmax(arr))

    if vmax <= vmin:
        vmax = vmin + 1e-6

    norm = (arr - vmin) / (vmax - vmin)
    norm = np.clip(norm, 0.0, 1.0)

    cmap_fn = cm.get_cmap(cmap)
    rgba = cmap_fn(norm)
    rgb = (rgba[..., :3] * 255).astype(np.uint8)
    return Image.fromarray(rgb)
