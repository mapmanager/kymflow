from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import czifile


@dataclass(frozen=True)
class CziPhysicalUnits:
    """Physical calibration values for a CZI scene.

    Attributes:
        seconds_per_line: Time spacing between adjacent samples on the T axis,
            in seconds. This is only meaningful for line-scan / kymograph-like
            data when a calibrated T coordinate is available. None if missing.
        um_per_pixel_x: Spatial calibration along the X axis, in micrometers
            per pixel. None if missing.
        um_per_pixel_y: Spatial calibration along the Y axis, in micrometers
            per pixel. None if missing.
    """

    seconds_per_line: Optional[float]
    um_per_pixel_x: Optional[float]
    um_per_pixel_y: Optional[float]


@dataclass(frozen=True)
class CziHeader:
    """Header information for the first scene of a CZI file.

    Attributes:
        path: Full path to the CZI file.
        shape: Raw array shape for the first scene.
        dims: Dimension labels for the first scene, in array order.
        sizes: Mapping from dimension label to number of elements.
        dtype: NumPy dtype of the scene pixel data.
        num_channels: Number of channels in the first scene.
        num_scenes: Number of scenes in the CZI file.
        physical_units: Physical calibration values extracted from scene
            coordinates when available.
    """

    path: str
    shape: tuple[int, ...]
    dims: tuple[str, ...]
    sizes: dict[str, int]
    dtype: np.dtype
    num_channels: int
    num_scenes: int
    physical_units: CziPhysicalUnits

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "shape": self.shape,
            "dims": self.dims,
            "sizes": self.sizes,
            "dtype": self.dtype,
            "num_channels": self.num_channels,
            # "num_scenes": self.num_scenes,
            "physical_units": self.physical_units,
        }

def _get_coord_step_as_float(coord: Any) -> Optional[float]:
    """Return the spacing between the first two coordinate values.

    Args:
        coord: One coordinate array-like object from an xarray coordinate map.

    Returns:
        The spacing between the first two values as a Python float, or None if
        fewer than two values are available.
    """
    if len(coord) < 2:
        return None
    return float((coord[1] - coord[0]).item())


def _extract_physical_units(scene: Any) -> CziPhysicalUnits:
    """Extract physical calibration values from a czifile scene.

    Args:
        scene: The first scene object returned by ``czifile.CziFile(...).scenes``.

    Returns:
        A ``CziPhysicalUnits`` instance with any available calibration values.
    """
    xarr = scene.asxarray()

    seconds_per_line: Optional[float] = None
    um_per_pixel_x: Optional[float] = None
    um_per_pixel_y: Optional[float] = None

    if "T" in xarr.coords:
        seconds_per_line = _get_coord_step_as_float(xarr.coords["T"])

    if "X" in xarr.coords:
        meters_per_pixel_x = _get_coord_step_as_float(xarr.coords["X"])
        if meters_per_pixel_x is not None:
            um_per_pixel_x = meters_per_pixel_x * 1e6

    if "Y" in xarr.coords:
        meters_per_pixel_y = _get_coord_step_as_float(xarr.coords["Y"])
        if meters_per_pixel_y is not None:
            um_per_pixel_y = meters_per_pixel_y * 1e6

    return CziPhysicalUnits(
        seconds_per_line=seconds_per_line,
        um_per_pixel_x=um_per_pixel_x,
        um_per_pixel_y=um_per_pixel_y,
    )


def _read_czi_header(path: str) -> CziHeader:
    """Read header information from the first scene of a CZI file.

    Args:
        path: Full path to a CZI file.

    Returns:
        A ``CziHeader`` instance for the first scene.
    """
    with czifile.CziFile(path) as czi_file:
        scenes = czi_file.scenes
        num_scenes = len(scenes)

        scene = scenes[0]
        shape = tuple(int(v) for v in scene.shape)
        dims = tuple(scene.dims)
        sizes = {str(k): int(v) for k, v in scene.sizes.items()}
        dtype = np.dtype(scene.dtype)
        num_channels = int(sizes["C"]) if "C" in sizes else 1
        physical_units = _extract_physical_units(scene)

    return CziHeader(
        path=path,
        shape=shape,
        dims=dims,
        sizes=sizes,
        dtype=dtype,
        num_channels=num_channels,
        num_scenes=num_scenes,
        physical_units=physical_units,
    )


def _load_first_scene_array(path: str) -> np.ndarray:
    """Load the full pixel array for the first scene of a CZI file.

    Args:
        path: Full path to a CZI file.

    Returns:
        NumPy array containing the full first-scene data.
    """
    with czifile.CziFile(path) as czi_file:
        return np.asarray(czi_file.scenes[0].asarray())


def _normalize_channel_to_yx(
    channel_data: np.ndarray,
    dims_without_c: tuple[str, ...],
) -> np.ndarray:
    """Normalize one channel of CZI data to a 2D ``(Y, X)`` array.

    Supported cases:
        - ``('T', 'X')``: kymograph-like line-scan data; T is treated as Y.
        - ``('Y', 'X')``: 2D image scan.
        - ``('X',)``: single-line data; expanded to shape ``(1, X)``.

    Args:
        channel_data: Pixel data for one channel after selecting the C axis.
        dims_without_c: Dimension labels after removing the C axis.

    Returns:
        A 2D NumPy array with shape ``(Y, X)``.

    Raises:
        ValueError: If the dimension layout is unsupported.
    """
    if dims_without_c == ("T", "X"):
        if channel_data.ndim != 2:
            raise ValueError(
                f"Expected 2D channel data for dims ('T', 'X'), got shape {channel_data.shape}"
            )
        return channel_data

    if dims_without_c == ("Y", "X"):
        if channel_data.ndim != 2:
            raise ValueError(
                f"Expected 2D channel data for dims ('Y', 'X'), got shape {channel_data.shape}"
            )
        return channel_data

    if dims_without_c == ("X",):
        if channel_data.ndim != 1:
            raise ValueError(
                f"Expected 1D channel data for dims ('X',), got shape {channel_data.shape}"
            )
        return np.expand_dims(channel_data, axis=0)

    raise ValueError(f"Unsupported CZI dims after channel selection: {dims_without_c}")


class MyCziImage:
    """Lazy-loading CZI reader for the first scene of a file.

    This class reads and stores header information during initialization, but
    does not load pixel data until requested.

    The class is intended for CZI files read with ``czifile`` and currently
    operates on scene 0 only.

    Attributes:
        path: Full path to the CZI file.
        header: Parsed header information for the first scene.
    """

    def __init__(self, path: str) -> None:
        """Initialize the reader and load header information.

        Args:
            path: Full path to a CZI file.
        """
        self.path = path
        self.header = _read_czi_header(path)
        self._img_data: Optional[np.ndarray] = None

    @property
    def shape(self) -> tuple[int, ...]:
        """Return the raw shape of the first scene.

        Returns:
            Raw array shape in file/native scene order.
        """
        return self.header.shape

    @property
    def dims(self) -> tuple[str, ...]:
        """Return the raw dimension labels of the first scene.

        Returns:
            Tuple of dimension labels in file/native scene order.
        """
        return self.header.dims

    @property
    def sizes(self) -> dict[str, int]:
        """Return the raw dimension sizes of the first scene.

        Returns:
            Mapping from dimension label to element count.
        """
        return self.header.sizes

    @property
    def dtype(self) -> np.dtype:
        """Return the pixel dtype of the first scene.

        Returns:
            NumPy dtype of the first-scene pixel data.
        """
        return self.header.dtype

    @property
    def num_channels(self) -> int:
        """Return the number of channels in the first scene.

        Returns:
            Number of channels.
        """
        return self.header.num_channels

    @property
    def num_scenes(self) -> int:
        """Return the number of scenes in the CZI file.

        Returns:
            Number of scenes.
        """
        return self.header.num_scenes

    @property
    def seconds_per_line(self) -> Optional[float]:
        """Return time spacing along the T axis, when available.

        Returns:
            Seconds per line for calibrated T coordinates, otherwise None.
        """
        return self.header.physical_units.seconds_per_line

    @property
    def um_per_pixel_x(self) -> Optional[float]:
        """Return X-axis spatial calibration, when available.

        Returns:
            Micrometers per pixel along X, otherwise None.
        """
        return self.header.physical_units.um_per_pixel_x

    @property
    def um_per_pixel_y(self) -> Optional[float]:
        """Return Y-axis spatial calibration, when available.

        Returns:
            Micrometers per pixel along Y, otherwise None.
        """
        return self.header.physical_units.um_per_pixel_y

    def load(self) -> np.ndarray:
        """Load and cache the full first-scene pixel array.

        Returns:
            Full first-scene NumPy array in native scene order.
        """
        if self._img_data is None:
            self._img_data = _load_first_scene_array(self.path)
        return self._img_data

    def unload(self) -> None:
        """Drop any cached pixel array.

        Returns:
            None.
        """
        self._img_data = None

    def load_channel(self, channel: int) -> np.ndarray:
        """Load one channel as a 2D ``(Y, X)`` array.

        Supported first-scene layouts:
            - ``('C', 'T', 'X')`` -> returned as ``(T, X)``
            - ``('C', 'Y', 'X')`` -> returned as ``(Y, X)``
            - ``('C', 'X')`` -> returned as ``(1, X)``

        Args:
            channel: Zero-based channel index to load.

        Returns:
            A 2D NumPy array with shape ``(Y, X)``.

        Raises:
            IndexError: If ``channel`` is outside the valid range.
            ValueError: If the file dimensions are unsupported.
        """
        if channel < 0 or channel >= self.num_channels:
            raise IndexError(
                f"Channel index {channel} out of range for {self.num_channels} channels"
            )

        if "C" not in self.dims:
            raise ValueError(f"CZI file has no channel axis: dims={self.dims}")

        arr = self.load()
        c_axis = self.dims.index("C")
        channel_data = np.take(arr, indices=channel, axis=c_axis)
        dims_without_c = tuple(dim for dim in self.dims if dim != "C")

        return _normalize_channel_to_yx(channel_data, dims_without_c)

    def as_dict(self) -> dict[str, Any]:
        """Return header information as a plain dictionary.

        Returns:
            Dictionary representation of the header.
        """
        return {
            "path": self.header.path,
            "shape": self.header.shape,
            "dims": self.header.dims,
            "sizes": self.header.sizes,
            "dtype": self.header.dtype,
            "num_channels": self.header.num_channels,
            "num_scenes": self.header.num_scenes,
            "seconds_per_line": self.header.physical_units.seconds_per_line,
            "um_per_pixel_x": self.header.physical_units.um_per_pixel_x,
            "um_per_pixel_y": self.header.physical_units.um_per_pixel_y,
        }

if __name__ == "__main__":
    from pprint import pprint

    path = '/Users/cudmore/Dropbox/data/sanpy-users/kym-users/czi-data/disjointedlinescansandframescans/Image 17.czi'

    czi = MyCziImage(path)

    pprint(czi.as_dict(), indent=4, width=120, sort_dicts=False)

    ch1 = czi.load_channel(1)
    print(f'loaded: {ch1.shape} {ch1.dtype} min:{ch1.min()} max:{ch1.max()}')
