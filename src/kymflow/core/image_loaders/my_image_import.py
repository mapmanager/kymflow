from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

import czifile
import oirfile


@dataclass(frozen=True)
class ImagePhysicalUnits:
    """Physical calibration values for an imported image.

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
class ImageHeader:
    """Header information for an imported image file.

    Attributes:
        path: Full path to the source file.
        shape: Raw array shape in file/native order.
        dims: Dimension labels in file/native order.
        sizes: Mapping from dimension label to number of elements.
        dtype: NumPy dtype of the pixel data.
        num_channels: Number of channels in the image.
        num_scenes: Number of scenes in the file. Kept for API compatibility;
            OIR uses ``1``.
        physical_units: Physical calibration values extracted from calibrated
            coordinates when available.
    """

    path: str
    shape: tuple[int, ...]
    dims: tuple[str, ...]
    sizes: dict[str, int]
    dtype: np.dtype
    num_channels: int
    num_scenes: int
    physical_units: ImagePhysicalUnits

    def as_dict(self) -> dict[str, Any]:
        """Return the header as a plain dictionary."""
        return {
            "path": self.path,
            "shape": self.shape,
            "dims": self.dims,
            "sizes": self.sizes,
            "dtype": self.dtype,
            "num_channels": self.num_channels,
            "physical_units": self.physical_units,
        }


def _get_step_from_coord(coord: Any) -> Optional[float]:
    """Return the spacing between the first two coordinate values.

    Args:
        coord: One coordinate array-like object.

    Returns:
        The spacing between the first two values as a Python float, or None if
        fewer than two values are available.
    """
    if coord is None or len(coord) < 2:
        return None

    value = coord[1] - coord[0]
    if hasattr(value, "item"):
        value = value.item()
    return float(value)


# -----------------------------------------------------------------------------
# CZI helpers
# -----------------------------------------------------------------------------

def _extract_czi_physical_units(scene: Any) -> ImagePhysicalUnits:
    """Extract physical calibration values from a czifile scene."""
    xarr = scene.asxarray()

    seconds_per_line: Optional[float] = None
    um_per_pixel_x: Optional[float] = None
    um_per_pixel_y: Optional[float] = None

    if "T" in xarr.coords:
        seconds_per_line = _get_step_from_coord(xarr.coords["T"])

    if "X" in xarr.coords:
        meters_per_pixel_x = _get_step_from_coord(xarr.coords["X"])
        if meters_per_pixel_x is not None:
            um_per_pixel_x = meters_per_pixel_x * 1e6

    if "Y" in xarr.coords:
        meters_per_pixel_y = _get_step_from_coord(xarr.coords["Y"])
        if meters_per_pixel_y is not None:
            um_per_pixel_y = meters_per_pixel_y * 1e6

    return ImagePhysicalUnits(
        seconds_per_line=seconds_per_line,
        um_per_pixel_x=um_per_pixel_x,
        um_per_pixel_y=um_per_pixel_y,
    )


def _read_czi_header(path: str) -> ImageHeader:
    """Read header information from the first scene of a CZI file."""
    with czifile.CziFile(path) as czi_file:
        scenes = czi_file.scenes
        num_scenes = len(scenes)

        scene = scenes[0]
        shape = tuple(int(v) for v in scene.shape)
        dims = tuple(scene.dims)
        sizes = {str(k): int(v) for k, v in scene.sizes.items()}
        dtype = np.dtype(scene.dtype)
        num_channels = int(sizes["C"]) if "C" in sizes else 1
        physical_units = _extract_czi_physical_units(scene)

    return ImageHeader(
        path=path,
        shape=shape,
        dims=dims,
        sizes=sizes,
        dtype=dtype,
        num_channels=num_channels,
        num_scenes=num_scenes,
        physical_units=physical_units,
    )


def _load_czi_first_scene_array(path: str) -> np.ndarray:
    """Load the full pixel array for the first scene of a CZI file."""
    with czifile.CziFile(path) as czi_file:
        return np.asarray(czi_file.scenes[0].asarray())


def _normalize_czi_channel_to_yx(
    channel_data: np.ndarray,
    dims_without_c: tuple[str, ...],
) -> np.ndarray:
    """Normalize one CZI channel to a 2D ``(Y, X)`` array.

    Supported cases:
        - ``('T', 'X')``: kymograph-like line-scan data; T is treated as Y.
        - ``('Y', 'X')``: 2D image scan.
        - ``('X',)``: single-line data; expanded to shape ``(1, X)``.
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


# -----------------------------------------------------------------------------
# OIR helpers
# -----------------------------------------------------------------------------

def _normalize_oir_to_cyx_singleton_extras(
    img_data: np.ndarray,
    dims: tuple[str, ...],
) -> Optional[np.ndarray]:
    """Normalize OIR image data to (C, Y, X) with singleton-only extra axes.

    Rules:
        - Y and X must exist.
        - C is optional; if missing, a singleton channel axis is inserted.
        - Any non-(C,Y,X) axis is accepted only when its size is 1 and is
          dropped by taking index 0.
        - Any non-(C,Y,X) axis with size > 1 is rejected.
    """
    dims_list = list(tuple(dims))
    arr = img_data

    if len(dims_list) != arr.ndim:
        return None

    if "Y" not in dims_list or "X" not in dims_list:
        return None

    idx = 0
    while idx < len(dims_list):
        axis_name = dims_list[idx]
        if axis_name in {"C", "Y", "X"}:
            idx += 1
            continue
        if arr.shape[idx] != 1:
            return None
        arr = np.take(arr, indices=0, axis=idx)
        dims_list.pop(idx)

    if "C" not in dims_list:
        arr = np.expand_dims(arr, axis=0)
        dims_list.insert(0, "C")

    perm = [dims_list.index("C"), dims_list.index("Y"), dims_list.index("X")]
    arr_cyx = np.transpose(arr, axes=perm)
    return arr_cyx if arr_cyx.ndim == 3 else None


def _extract_oir_physical_units(oir: Any) -> ImagePhysicalUnits:
    """Extract physical calibration values from an OIR file.

    Uses ``oir.coords`` as the source of truth. The coordinate arrays are
    already calibrated in physical units by ``oirfile``. This function takes
    the step between the first two values for T, X, and Y when available.

    Notes:
        - T is treated as seconds-per-line when present.
        - X and Y are treated as micrometers-per-pixel.
        - Missing or length<2 coordinate arrays yield None.
    """
    coords = oir.coords

    print(f'coords:')
    print(coords)

    return ImagePhysicalUnits(
        seconds_per_line=_get_step_from_coord(coords.get("X")),  # abb FIX THIS
        um_per_pixel_x=_get_step_from_coord(coords.get("X")),
        um_per_pixel_y=_get_step_from_coord(coords.get("Y")),
    )


def _read_oir_header(path: str) -> ImageHeader:
    """Read header information from an OIR file.

    Supported normalized layouts are strictly CYX-compatible with only
    singleton extra axes.
    """
    path_obj = Path(path)

    with oirfile.OirFile(path_obj) as oir:
        dims = tuple(str(dim) for dim in oir.dims)
        img_data = np.asarray(oir.asarray())
        coords = oir.coords  # force access while file is open
        _ = coords
        cyx_data = _normalize_oir_to_cyx_singleton_extras(img_data, dims)
        physical_units = _extract_oir_physical_units(oir)

    if cyx_data is None:
        raise ValueError(
            f"Unsupported OIR dims {dims} with shape {tuple(int(x) for x in img_data.shape)}; "
            "expected CYX-compatible dims with only singleton extras"
        )

    shape_raw = tuple(int(x) for x in img_data.shape)
    sizes = {dim: int(size) for dim, size in zip(dims, shape_raw, strict=False)}
    dtype = np.dtype(img_data.dtype)
    num_channels = int(cyx_data.shape[0])

    return ImageHeader(
        path=str(path_obj),
        shape=shape_raw,
        dims=dims,
        sizes=sizes,
        dtype=dtype,
        num_channels=num_channels,
        num_scenes=1,
        physical_units=physical_units,
    )


def _load_oir_array(path: str) -> np.ndarray:
    """Load the full raw pixel array from an OIR file."""
    with oirfile.OirFile(path) as oir:
        return np.asarray(oir.asarray())


def _normalize_oir_channel_to_yx(
    img_data: np.ndarray,
    dims: tuple[str, ...],
    channel: int,
) -> np.ndarray:
    """Load one OIR channel as a 2D ``(Y, X)`` array.

    Supported cases are CYX-compatible layouts with only singleton extra axes.
    After singleton extras are removed and a missing channel axis is inserted,
    one channel is selected and returned as a 2D ``(Y, X)`` image.
    """
    arr_cyx = _normalize_oir_to_cyx_singleton_extras(img_data, dims)
    if arr_cyx is None:
        raise ValueError(
            f"Unsupported OIR dims {dims} with shape {img_data.shape}; "
            "expected CYX-compatible dims with only singleton extras"
        )

    if channel < 0 or channel >= arr_cyx.shape[0]:
        raise IndexError(
            f"Channel index {channel} out of range for {arr_cyx.shape[0]} channels"
        )

    return np.asarray(arr_cyx[channel])


class MyCziImage:
    """Lazy-loading CZI reader for the first scene of a file.

    This class reads and stores header information during initialization, but
    does not load pixel data until requested. The class operates on scene 0
    only.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.header = _read_czi_header(path)
        self._img_data: Optional[np.ndarray] = None

    @property
    def shape(self) -> tuple[int, ...]:
        return self.header.shape

    @property
    def dims(self) -> tuple[str, ...]:
        return self.header.dims

    @property
    def sizes(self) -> dict[str, int]:
        return self.header.sizes

    @property
    def dtype(self) -> np.dtype:
        return self.header.dtype

    @property
    def num_channels(self) -> int:
        return self.header.num_channels

    @property
    def num_scenes(self) -> int:
        return self.header.num_scenes

    @property
    def seconds_per_line(self) -> Optional[float]:
        return self.header.physical_units.seconds_per_line

    @property
    def um_per_pixel_x(self) -> Optional[float]:
        return self.header.physical_units.um_per_pixel_x

    @property
    def um_per_pixel_y(self) -> Optional[float]:
        return self.header.physical_units.um_per_pixel_y

    def load(self) -> np.ndarray:
        if self._img_data is None:
            self._img_data = _load_czi_first_scene_array(self.path)
        return self._img_data

    def unload(self) -> None:
        self._img_data = None

    def load_channel(self, channel: int) -> np.ndarray:
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
        return _normalize_czi_channel_to_yx(channel_data, dims_without_c)

    def as_dict(self) -> dict[str, Any]:
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


class MyOirImage:
    """Lazy-loading OIR reader with an API aligned to ``MyCziImage``.

    This class reads and stores header information during initialization, but
    does not load pixel data until requested.

    Supported OIR layouts are strictly CYX-compatible with only singleton
    extra axes. Non-singleton extra axes are rejected rather than guessed.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.header = _read_oir_header(path)
        self._img_data: Optional[np.ndarray] = None

    @property
    def shape(self) -> tuple[int, ...]:
        return self.header.shape

    @property
    def dims(self) -> tuple[str, ...]:
        return self.header.dims

    @property
    def sizes(self) -> dict[str, int]:
        return self.header.sizes

    @property
    def dtype(self) -> np.dtype:
        return self.header.dtype

    @property
    def num_channels(self) -> int:
        return self.header.num_channels

    @property
    def num_scenes(self) -> int:
        return self.header.num_scenes

    @property
    def seconds_per_line(self) -> Optional[float]:
        return self.header.physical_units.seconds_per_line

    @property
    def um_per_pixel_x(self) -> Optional[float]:
        return self.header.physical_units.um_per_pixel_x

    @property
    def um_per_pixel_y(self) -> Optional[float]:
        return self.header.physical_units.um_per_pixel_y

    def load(self) -> np.ndarray:
        if self._img_data is None:
            self._img_data = _load_oir_array(self.path)
        return self._img_data

    def unload(self) -> None:
        self._img_data = None

    def load_channel(self, channel: int) -> np.ndarray:
        arr = self.load()
        return _normalize_oir_channel_to_yx(arr, self.dims, channel)

    def as_dict(self) -> dict[str, Any]:
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

if __name__ == '__main__':
    from pprint import pprint

    path = '/Users/cudmore/Dropbox/data/arsalan/20190416/20190416_b_0021.oir'
    oir = MyOirImage(path)
    print(f'oir.header:')
    pprint(oir.header.as_dict(), indent=4, width=120, sort_dicts=False)
    img_data = oir.load_channel(0)
    print(f'img_data: {img_data.shape} {img_data.dtype} min:{img_data.min()} max:{img_data.max()}')