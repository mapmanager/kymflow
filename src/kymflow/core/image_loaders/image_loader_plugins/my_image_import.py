from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Optional, TypeVar

import numpy as np

import czifile
import oirfile
import tifffile

from kymflow.core.image_loaders.image_loader_plugins.olympus_txt_kym import (
    read_olympus_txt_dict,
)
from kymflow.core.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

def _build_file_list(path: str | Path, file_types: list[str]) -> list[str]:
    """Build a list of files in the given path.

    Recursively traverse into path and build a list of files with the given types.

    Args:
        path: The path to traverse.
        file_types: The types of files to include in the list (no dot extension)

    Returns:
        A list of absolute file paths.
    """
    allowed_exts = {f".{ext.lower().lstrip('.')}" for ext in file_types}
    result: list[str] = []

    for root, _dirs, filenames in os.walk(str(path)):
        for filename in filenames:
            file_path = Path(root) / filename
            if file_path.suffix.lower() in allowed_exts:
                result.append(str(file_path.resolve()))
    return result


@dataclass(frozen=True)
class PlotlyHeatmapUniformAxes2D:
    """Uniform grid for :class:`plotly.graph_objects.Heatmap` with ``z = arr.transpose()``."""

    x0: float
    dx: float
    y0: float
    dy: float
    x_title: str
    y_title: str
    x_range: tuple[float, float]
    y_range: tuple[float, float]


@dataclass(frozen=True)
class ImageHeader:
    """Header information for an imported image file.

    Attributes:
        path: Filesystem path when loading from disk, or the upload **filename**
            when loading from a binary stream (not necessarily on disk).
        shape: Raw array shape in file/native order.
        dims: Dimension labels in file/native order.
        sizes: Mapping from dimension label to number of elements.
        dtype: NumPy dtype of the pixel data.
        num_channels: Number of channels in the image.
        num_scenes: Number of scenes in the file (OIR uses ``1``).
        physical_units: Per-axis calibration steps or placeholders from the file.
        physical_units_labels: Human-readable labels aligned with ``physical_units``.
        date: Acquisition calendar date as ``YYYYMMDD``, or ``""`` if unknown.
        time: Acquisition time-of-day as ``HH:MM:SS`` (24-hour), or ``""`` if unknown.
    """

    path: str
    shape: tuple[int, ...]
    dims: tuple[str, ...]
    sizes: dict[str, int]
    dtype: np.dtype
    num_channels: int
    num_scenes: int
    physical_units: tuple[Any, ...]
    physical_units_labels: tuple[str, ...]
    date: str = ""
    time: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Return the header as a plain dictionary."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def as_json_dict(self) -> dict[str, Any]:
        """Return a dict suitable for :func:`json.dumps` (dtype as string, NaN/inf → None)."""
        d = self.as_dict()
        fixed_units: list[Any] = []
        for x in d["physical_units"]:
            if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
                fixed_units.append(None)
            else:
                fixed_units.append(x)
        return {
            "path": d["path"],
            "shape": list(d["shape"]),
            "dims": list(d["dims"]),
            "sizes": dict(d["sizes"]),
            "dtype": str(d["dtype"]),
            "num_channels": d["num_channels"],
            "num_scenes": d["num_scenes"],
            "physical_units": fixed_units,
            "physical_units_labels": list(d["physical_units_labels"]),
            "date": d["date"],
            "time": d["time"],
        }

    @staticmethod
    def default_physical_for_dims(
        dims: tuple[str, ...],
    ) -> tuple[tuple[float, ...], tuple[str, ...]]:
        """Default per-axis calibration when unknown (e.g. TIFF).

        Args:
            dims: Axis labels; one value per axis.

        Returns:
            ``physical_units`` all ``1.0`` and ``physical_units_labels`` all ``\"Pixels\"``.
        """
        n = len(dims)
        units = tuple(1.0 for _ in range(n))
        labels = tuple("Pixels" for _ in range(n))
        return units, labels

    def _physical_step_for_dim(self, dim: str) -> float | None:
        """Return a finite positive calibration step for ``dim``, or ``None`` if unknown."""
        if dim not in self.dims:
            return None
        i = self.dims.index(dim)
        if i >= len(self.physical_units):
            return None
        u = self.physical_units[i]
        if u is None:
            return None
        if isinstance(u, float) and (math.isnan(u) or math.isinf(u)):
            return None
        try:
            v = float(u)
        except (TypeError, ValueError):
            return None
        if v <= 0.0 or math.isnan(v) or math.isinf(v):
            return None
        return v

    def _physical_label_for_dim(self, dim: str) -> str:
        if dim not in self.dims:
            return dim
        i = self.dims.index(dim)
        if i < len(self.physical_units_labels):
            lab = self.physical_units_labels[i]
            if lab:
                return str(lab)
        return dim

    def plotly_heatmap_uniform_axes_for_transpose_z(
        self,
        slice_shape_yx: tuple[int, int],
    ) -> PlotlyHeatmapUniformAxes2D:
        """Uniform ``x0``/``dx`` and ``y0``/``dy`` for a Plotly heatmap with ``z = arr.transpose()``.

        ``arr`` must have shape ``(nY, nX)`` = ``(Y, X)``. Then ``z = arr.T`` has shape
        ``(nX, nY)``; Plotly ``x`` uses **Y** calibration (``nY`` columns of ``z``) and ``y``
        uses **X** calibration (``nX`` rows of ``z``). Steps and titles come from
        :attr:`physical_units` / :attr:`physical_units_labels` aligned with :attr:`dims`.

        When :meth:`_physical_step_for_dim` is ``None`` for an axis, use pixel-style spacing
        ``x0=0``, ``dx=1`` (coordinates ``0 .. n-1``), matching the previous list fallback.

        When a positive step exists, use cell-centered spacing ``x0 = step/2``, ``dx = step``
        (column ``j`` at ``x0 + j * dx`` = ``(j + 0.5) * step``).

        ``x_range`` / ``y_range`` are half-cell padded extents for ``layout.xaxis.range`` /
        ``layout.yaxis.range``.
        """
        n_y, n_x = int(slice_shape_yx[0]), int(slice_shape_yx[1])

        def axis_uniform(n: int, dim: str) -> tuple[float, float, str, tuple[float, float]]:
            step = self._physical_step_for_dim(dim)
            label = self._physical_label_for_dim(dim)
            if step is None:
                x0, dx = 0.0, 1.0
            else:
                x0, dx = 0.5 * step, step
            if n <= 0:
                return x0, dx, label, (0.0, 0.0)
            lo = x0 - 0.5 * dx
            hi = x0 + (n - 1) * dx + 0.5 * dx
            return x0, dx, label, (float(lo), float(hi))

        x0, dx, x_title, x_range = axis_uniform(n_y, "Y")
        y0, dy, y_title, y_range = axis_uniform(n_x, "X")
        return PlotlyHeatmapUniformAxes2D(
            x0=x0,
            dx=dx,
            y0=y0,
            dy=dy,
            x_title=x_title,
            y_title=y_title,
            x_range=x_range,
            y_range=y_range,
        )


def preview_yx_shape_hint(header: ImageHeader) -> str:
    """Human-readable expected 2D preview dimensions (Y×X) from header metadata.

    Used for progress messages; does not load pixels. Falls back to ``shape``/``dims``
    when ``Y``/``X`` are not in :attr:`ImageHeader.sizes`.
    """
    sizes = header.sizes
    if "Y" in sizes and "X" in sizes:
        return f"{sizes['Y']}×{sizes['X']}"
    return _preview_yx_shape_fallback(header.shape, header.dims)


def preview_yx_shape_hint_from_catalog_record(rec: Mapping[str, Any]) -> str:
    """Same as :func:`preview_yx_shape_hint` using a flattened catalog row dict.

    Expects optional ``sizes``, ``shape``, and ``dims`` keys as in
    :meth:`~ImageHeader.as_json_dict` / folder catalog records.
    """
    sizes = rec.get("sizes")
    if isinstance(sizes, dict) and "Y" in sizes and "X" in sizes:
        return f"{sizes['Y']}×{sizes['X']}"
    shape = rec.get("shape")
    dims = rec.get("dims")
    if isinstance(shape, list) and isinstance(dims, list) and "Y" in dims and "X" in dims:
        iy = dims.index("Y")
        ix = dims.index("X")
        if iy < len(shape) and ix < len(shape):
            return f"{shape[iy]}×{shape[ix]}"
    if isinstance(shape, list):
        return f"shape {shape}"
    if dims is not None:
        return f"dims {dims!s}"
    return "shape TBD"


def _preview_yx_shape_fallback(shape: tuple[int, ...], dims: tuple[str, ...]) -> str:
    if "Y" in dims and "X" in dims:
        iy = dims.index("Y")
        ix = dims.index("X")
        if iy < len(shape) and ix < len(shape):
            return f"{shape[iy]}×{shape[ix]}"
    return f"shape {shape} dims {dims}"


_LoaderT = TypeVar("_LoaderT", bound="ImageLoaderBase")


def _dtype_from_olympus_bits(bits: int | None) -> np.dtype:
    if bits is None:
        return np.dtype(np.uint16)
    if bits <= 8:
        return np.dtype(np.uint8)
    if bits <= 16:
        return np.dtype(np.uint16)
    return np.dtype(np.uint32)


def _iso8601_datetime_str_to_yyyymmdd_hhmmss(s: str) -> tuple[str, str]:
    """Parse oirfile-style ISO 8601 string; return ``(YYYYMMDD, HH:MM:SS)`` or empty strings."""
    t = s.strip()
    if not t:
        return ("", "")
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return ("", "")
    return (dt.strftime("%Y%m%d"), dt.strftime("%H:%M:%S"))


def _olympus_combined_datetime_to_yyyymmdd_hhmmss(combined: str | None) -> tuple[str, str]:
    """Parse Olympus ``.txt`` combined US-style date/time line."""
    if combined is None:
        return ("", "")
    c = str(combined).strip()
    if not c:
        return ("", "")
    fmts = (
        "%m/%d/%Y %I:%M:%S.%f %p",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S.%f",
        "%m/%d/%Y %H:%M:%S",
    )
    for fmt in fmts:
        try:
            dt = datetime.strptime(c, fmt)
            return (dt.strftime("%Y%m%d"), dt.strftime("%H:%M:%S"))
        except ValueError:
            continue
    return ("", "")


def _olympus_legacy_date_time_parts(
    date_str: object | None,
    time_str: object | None,
) -> tuple[str, str]:
    """Fallback when ``olympusDateTimeCombined`` is absent (best-effort)."""
    date_out = ""
    if isinstance(date_str, str) and date_str.strip():
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                date_out = datetime.strptime(date_str.strip(), fmt).strftime("%Y%m%d")
                break
            except ValueError:
                continue
    time_out = ""
    if isinstance(time_str, str) and time_str.strip():
        for fmt in ("%H:%M:%S", "%I:%M:%S %p", "%I:%M:%S.%f %p"):
            try:
                time_out = datetime.strptime(time_str.strip(), fmt).strftime("%H:%M:%S")
                break
            except ValueError:
                continue
    return (date_out, time_out)


def image_header_from_olympus_dict(path: str, d: dict[str, Any]) -> ImageHeader:
    """Build :class:`ImageHeader` from :func:`~olympus_txt_kym.read_olympus_txt_dict` output.

    Kymograph axes: ``Y`` = lines (time), ``X`` = pixels (space), matching 2D TIFF policy.
    """
    nl = d.get("numLines")
    pl = d.get("pixelsPerLine")
    spl = d.get("secondsPerLine")
    um = d.get("umPerPixel")
    if nl is None or pl is None or spl is None or um is None:
        raise ValueError(
            f"Olympus dict missing required fields for ImageHeader: "
            f"numLines={nl!r} pixelsPerLine={pl!r} secondsPerLine={spl!r} umPerPixel={um!r}"
        )
    shape = (int(nl), int(pl))
    dims = ("Y", "X")
    sizes = {"Y": shape[0], "X": shape[1]}
    bp = d.get("bitsPerPixel")
    bits: int | None
    if bp is None:
        bits = None
    else:
        try:
            bits = int(bp)
        except (TypeError, ValueError):
            bits = None
    dtype = _dtype_from_olympus_bits(bits)
    num_channels = int(d.get("numChannels", 1))
    physical_units = (float(spl), float(um))
    physical_units_labels = ("seconds", "um")
    combined = d.get("olympusDateTimeCombined")
    if isinstance(combined, str) and combined.strip():
        date_s, time_s = _olympus_combined_datetime_to_yyyymmdd_hhmmss(combined)
    else:
        date_s, time_s = _olympus_legacy_date_time_parts(
            d.get("dateStr"),
            d.get("timeStr"),
        )
    return ImageHeader(
        path=path,
        shape=shape,
        dims=dims,
        sizes=sizes,
        dtype=dtype,
        num_channels=num_channels,
        num_scenes=1,
        physical_units=physical_units,
        physical_units_labels=physical_units_labels,
        date=date_s,
        time=time_s,
    )


def _tif_dims_from_ndim(ndim: int) -> tuple[str, ...]:
    """Map TIFF array rank to axis labels (explicit; extend here for new policies)."""
    if ndim == 2:
        return ("Y", "X")
    if ndim == 3:
        return ("Z", "Y", "X")
    if ndim == 4:
        return ("C", "Z", "Y", "X")
    raise ValueError(f"Unsupported TIFF ndim {ndim}; expected 2, 3, or 4")


class ImageLoaderBase:
    """Base class for lazy-loading image readers with a shared header and pixel API."""

    @staticmethod
    def _step_from_coord(coord: Any) -> Optional[float]:
        """Spacing between the first two samples of a 1D coordinate array.

        Args:
            coord: One-dimensional coordinate array-like, or ``None``.

        Returns:
            Difference as ``float``, or ``None`` if fewer than two points.
        """
        if coord is None or len(coord) < 2:
            return None

        value = coord[1] - coord[0]
        if hasattr(value, "item"):
            value = value.item()
        return float(value)

    def __init__(self, path: str, header: ImageHeader | None = None) -> None:
        """Load metadata from disk unless a precomputed header is supplied.

        Args:
            path: Filesystem path to the image file.
            header: Optional pre-built header; if omitted, :meth:`read_header` is used.
        """
        self.path = path
        self._stream: BinaryIO | None = None
        self._img_data: Optional[np.ndarray] = None
        if header is None:
            self._header = self.read_header()
        else:
            self._header = header

    def read_header(self) -> ImageHeader:
        """Read header metadata for this loader's path.

        Returns:
            Parsed :class:`ImageHeader`.

        Raises:
            NotImplementedError: If the concrete subclass does not implement this.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement read_header()")

    @classmethod
    def read_header_from_path(cls, path: str) -> ImageHeader:
        """Read header from disk without keeping the loader instance.

        Args:
            path: Filesystem path to the image file.

        Returns:
            Parsed :class:`ImageHeader`.
        """
        return cls(path).header

    def _image_header_from_scene(
        self,
        path: str,
        scene: Any,
        num_scenes: int,
    ) -> ImageHeader:
        """Build an :class:`ImageHeader` from a czifile/oirfile scene-like object.

        Args:
            path: Absolute or resolved path stored on the header.
            scene: Object with ``shape``, ``dims``, ``sizes``, and ``dtype``.
            num_scenes: Total scene count for the file (OIR uses ``1``).

        Returns:
            Frozen :class:`ImageHeader` instance.
        """
        shape = tuple(int(v) for v in scene.shape)
        dims = tuple(str(d) for d in scene.dims)
        sizes = {str(k): int(v) for k, v in scene.sizes.items()}
        dtype = np.dtype(scene.dtype)
        num_channels = int(sizes["C"]) if "C" in sizes else 1
        physical_units, physical_units_labels = self._physical_units_for_header(scene)
        date_s, time_s = self._date_time_for_header(scene)
        return ImageHeader(
            path=path,
            shape=shape,
            dims=dims,
            sizes=sizes,
            dtype=dtype,
            num_channels=num_channels,
            num_scenes=num_scenes,
            physical_units=physical_units,
            physical_units_labels=physical_units_labels,
            date=date_s,
            time=time_s,
        )

    def _date_time_for_header(self, scene: Any) -> tuple[str, str]:
        """Acquisition date/time strings for scene-based headers (OIR fills; CZI/TIF use ``\"\"``)."""
        return ("", "")

    def _physical_units_for_header(self, scene: Any) -> tuple[tuple[Any, ...], tuple[str, ...]]:
        """Subclass hook: physical units for :meth:`_image_header_from_scene`.

        Implementations receive the same ``scene`` object passed to
        :meth:`_image_header_from_scene` (format-specific).

        Raises:
            NotImplementedError: If not implemented by a subclass that uses
                :meth:`_image_header_from_scene`.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement _physical_units_for_header()"
        )

    def _load_full_image_array(self) -> np.ndarray:
        """Load the full pixel array for this loader's active scene(s).

        Returns:
            NumPy array in native dimension order.

        Raises:
            NotImplementedError: If the subclass does not implement loading.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement _load_full_image_array()"
        )

    def load_image_data(self) -> np.ndarray:
        """Load and cache the full image array (lazy, idempotent).

        Returns:
            The full pixel array for this file/scene.
        """
        if self._img_data is None:
            self._img_data = self._load_full_image_array()
        return self._img_data

    def unload_image_data(self) -> None:
        """Drop cached pixel data; header is unchanged."""
        self._img_data = None

    @staticmethod
    def array_for_plotly_display(image: np.ndarray) -> np.ndarray:
        """Return a ``uint8`` array for GUI heatmaps (e.g. NiceGUI Plotly); pixel caches unchanged.

        Use this only for display. Analysis should keep using :meth:`get_slice_data` /
        :meth:`load_image_data` at full :attr:`~ImageHeader.dtype`.

        - **uint8**: returned contiguous, no rescaling.
        - **uint16**: linear min–max stretch to 0–255 (full dynamic range for display).
        - **Other numeric dtypes**: same min–max stretch to ``uint8``.

        Constant arrays become all zeros.
        """
        if image.dtype == np.uint8:
            return np.ascontiguousarray(image)
        if image.dtype == np.uint16:
            a = image.astype(np.float32, copy=False)
            vmin = float(a.min())
            vmax = float(a.max())
            if vmax <= vmin:
                return np.zeros(image.shape, dtype=np.uint8)
            scale = 255.0 / (vmax - vmin)
            return ((a - vmin) * scale).astype(np.uint8)
        a = np.asarray(image, dtype=np.float64)
        vmin = float(a.min())
        vmax = float(a.max())
        if vmax <= vmin:
            return np.zeros(image.shape, dtype=np.uint8)
        return ((a - vmin) / (vmax - vmin) * 255.0).astype(np.uint8)

    @property
    def header(self) -> ImageHeader:
        """Header read at construction or injected."""
        return self._header

    def get_slice_data(self, channel: int, z: int = 0, t: int = 0) -> np.ndarray:
        """Return a single 2D ``(Y, X)`` slice after optional ``T``/``Z``/``C`` selection.

        Loads pixel data on first use.

        Args:
            channel: Channel index along ``C`` (or ``0`` when there is no ``C`` axis).
            z: Index along ``Z`` if present; ignored if ``Z`` is absent.
            t: Index along ``T`` if present; ignored if ``T`` is absent.

        Returns:
            Two-dimensional array with dimensions ``(Y, X)``.

        Raises:
            IndexError: If any index is out of range.
            ValueError: If dims cannot be reduced to ``(Y, X)``.
        """
        self.load_image_data()
        if channel < 0 or channel >= self._header.num_channels:
            raise IndexError(
                f"Channel index {channel} out of range for {self._header.num_channels} channels"
            )

        dims = list(self._header.dims)
        if "Y" not in dims or "X" not in dims:
            raise ValueError(
                f"Expected dims to include Y and X; got dims={self._header.dims}"
            )

        if "C" not in dims:
            if self._header.num_channels != 1:
                raise ValueError(
                    f"No C axis in dims but num_channels={self._header.num_channels}"
                )
            if channel != 0:
                raise IndexError(f"No C axis; only channel 0 is valid, got {channel}")

        assert self._img_data is not None
        arr = self._img_data

        def _take_and_drop(dim_label: str, index: int) -> None:
            nonlocal arr, dims
            if dim_label not in dims:
                return
            axis = dims.index(dim_label)
            size = arr.shape[axis]
            if index < 0 or index >= size:
                raise IndexError(
                    f"{dim_label} index {index} out of range for size {size} (dims={tuple(dims)})"
                )
            arr = np.take(arr, indices=index, axis=axis)
            dims.pop(axis)

        _take_and_drop("T", t)
        _take_and_drop("Z", z)
        if "C" in dims:
            _take_and_drop("C", channel)

        if tuple(dims) != ("Y", "X"):
            raise ValueError(
                f"After selecting T/Z/C, expected remaining dims (Y, X); got {tuple(dims)} "
                f"with shape {arr.shape}"
            )

        return arr

    def get_channel_data(self, channel: int) -> np.ndarray:
        """Return the full array for one channel (``C`` axis removed).

        Loads pixel data on first use. Remaining dimensions stay in file order
        (e.g. ``T, Y, X`` or ``Z, Y, X``).

        Args:
            channel: Index along the ``C`` dimension, or ``0`` when there is no ``C`` axis.

        Returns:
            NumPy array without the channel axis.

        Raises:
            IndexError: If ``channel`` is invalid.
            ValueError: If the header implies multiple channels but there is no ``C`` dim.
        """
        self.load_image_data()
        if channel < 0 or channel >= self._header.num_channels:
            raise IndexError(
                f"Channel index {channel} out of range for {self._header.num_channels} channels"
            )

        if "C" not in self._header.dims:
            if self._header.num_channels != 1:
                raise ValueError(
                    f"No C axis in dims but num_channels={self._header.num_channels}"
                )
            if channel != 0:
                raise IndexError(f"No C axis; only channel 0 is valid, got {channel}")
            assert self._img_data is not None
            return self._img_data

        assert self._img_data is not None
        c_axis = self._header.dims.index("C")
        return np.take(self._img_data, indices=channel, axis=c_axis)


def _init_loader_from_stream(
    cls: type[_LoaderT],
    stream: BinaryIO,
    filename: str,
    header: ImageHeader | None,
) -> _LoaderT:
    """Construct a loader instance from a stream (shared by OIR/CZI ``from_stream``)."""
    inst = object.__new__(cls)
    inst.path = filename
    inst._stream = stream
    inst._img_data = None
    if hasattr(cls, "_squeeze"):
        inst._squeeze = getattr(cls, "_squeeze")
    if header is None:
        inst._header = inst.read_header()
    else:
        inst._header = header
    return inst


class MyOirImage(ImageLoaderBase):
    """Lazy-loading OIR reader aligned with :class:`MyCziImage`.

    Pixel data loads on demand. Supported OIR layouts follow the same CYX
    constraints as the helper functions in this module.
    """

    _squeeze = True

    def __init__(self, path: str, header: ImageHeader | None = None) -> None:
        super().__init__(path, header)

    @classmethod
    def from_stream(
        cls,
        stream: BinaryIO,
        filename: str,
        header: ImageHeader | None = None,
    ) -> MyOirImage:
        """Load from a seekable binary stream (e.g. upload ``BytesIO``).

        The stream is not closed by this class; callers may ``seek(0)`` between
        header and pixel reads internally.

        Args:
            stream: Seekable ``IO[bytes]`` (``oirfile`` requires ``seek``/``tell``).
            filename: Original basename or full name; stored on :attr:`path` / header.
            header: Optional pre-built header.

        Returns:
            Configured :class:`MyOirImage` instance.
        """
        return _init_loader_from_stream(cls, stream, filename, header)

    @classmethod
    def read_header_from_stream(cls, stream: BinaryIO, filename: str) -> ImageHeader:
        """Read OIR header from a stream without retaining the loader."""
        return cls.from_stream(stream, filename).header

    def read_header(self) -> ImageHeader:
        return self._read_oir_header()

    def _physical_units_for_header(self, scene: Any) -> tuple[tuple[Any, ...], tuple[str, ...]]:
        oir = scene
        coords = oir.coords
        n = len(coords)
        physical_units: list[Any] = [None] * n
        physical_units_labels = [""] * n
        for idx, coord_str in enumerate(coords):
            physical_units[idx] = ImageLoaderBase._step_from_coord(coords[coord_str])
            physical_units_labels[idx] = coord_str
        return tuple(physical_units), tuple(physical_units_labels)

    def _date_time_for_header(self, scene: Any) -> tuple[str, str]:
        oir = scene
        raw = getattr(oir, "datetime", None)
        if raw is None:
            return ("", "")
        return _iso8601_datetime_str_to_yyyymmdd_hhmmss(str(raw))

    def _read_oir_header(self) -> ImageHeader:
        logical = self.path
        if self._stream is not None:
            self._stream.seek(0)
            with oirfile.OirFile(self._stream, squeeze=self._squeeze) as oir_file:
                return self._image_header_from_scene(logical, oir_file, num_scenes=1)
        path = self.path
        with oirfile.OirFile(path, squeeze=self._squeeze) as oir_file:
            return self._image_header_from_scene(path, oir_file, num_scenes=1)

    def _load_full_image_array(self) -> np.ndarray:
        logger.info('')
        if self._stream is not None:
            self._stream.seek(0)
            with oirfile.OirFile(self._stream, squeeze=self._squeeze) as oir:
                return np.asarray(oir.asarray())
        with oirfile.OirFile(self.path, squeeze=self._squeeze) as oir:
            return np.asarray(oir.asarray())


class MyCziImage(ImageLoaderBase):
    """Lazy-loading CZI reader for scene ``0`` only."""

    def __init__(self, path: str, header: ImageHeader | None = None) -> None:
        super().__init__(path, header)

    @classmethod
    def from_stream(
        cls,
        stream: BinaryIO,
        filename: str,
        header: ImageHeader | None = None,
    ) -> MyCziImage:
        """Load from a seekable binary stream (e.g. upload ``BytesIO``).

        Args:
            stream: Seekable ``IO[bytes]``.
            filename: Original name; stored on :attr:`path` / header.
            header: Optional pre-built header.

        Returns:
            Configured :class:`MyCziImage` instance.
        """
        return _init_loader_from_stream(cls, stream, filename, header)

    @classmethod
    def read_header_from_stream(cls, stream: BinaryIO, filename: str) -> ImageHeader:
        """Read CZI header from a stream without retaining the loader."""
        return cls.from_stream(stream, filename).header

    def read_header(self) -> ImageHeader:
        return self._read_czi_header()

    def _physical_units_for_header(self, scene: Any) -> tuple[tuple[Any, ...], tuple[str, ...]]:
        czi_scene = scene
        xarr = czi_scene.asxarray()
        n = len(xarr.coords)
        _physical_units: list[Any] = [None] * n
        _physical_units_labels = [""] * n
        for idx, coord_str in enumerate(xarr.coords):
            if xarr[coord_str] is None or len(xarr[coord_str]) < 2:
                _physical_units[idx] = None
                _physical_units_labels[idx] = "unknown"
                continue
            value0 = xarr[coord_str][1] - xarr[coord_str][0]
            value: Any = value0.item()
            if coord_str in ("X", "Y"):
                value = float(value) * 1e6
            elif coord_str == "C":
                value = float("nan")
            _physical_units[idx] = value
            if coord_str in ("X", "Y"):
                _physical_units_labels[idx] = "um"
            elif coord_str == "T":
                _physical_units_labels[idx] = "seconds"
            else:
                _physical_units_labels[idx] = "unknown"

        return tuple(_physical_units), tuple(_physical_units_labels)

    def _read_czi_header(self) -> ImageHeader:
        """Read header information from the first scene of a CZI file.

        Common dimension patterns include ``('C','T','X')`` (line-scan),
        ``('C','T','Y','X')`` (frames), and ``('C','Y','X')`` (2D).
        """
        logical = self.path
        if self._stream is not None:
            self._stream.seek(0)
            with czifile.CziFile(self._stream) as czi_file:
                num_scenes = len(czi_file.scenes)
                scene = czi_file.scenes[0]
                return self._image_header_from_scene(logical, scene, num_scenes=num_scenes)
        path = self.path
        with czifile.CziFile(path) as czi_file:
            num_scenes = len(czi_file.scenes)
            scene = czi_file.scenes[0]
            return self._image_header_from_scene(path, scene, num_scenes=num_scenes)

    def _load_full_image_array(self) -> np.ndarray:
        logger.info('')
        if self._stream is not None:
            self._stream.seek(0)
            with czifile.CziFile(self._stream) as czi_file:
                return np.asarray(czi_file.scenes[0].asarray())
        with czifile.CziFile(self.path) as czi_file:
            return np.asarray(czi_file.scenes[0].asarray())


class MyTifImage(ImageLoaderBase):
    """TIFF reader using ``tifffile.imread``; header from pixels and/or Olympus sidecar ``.txt``.

    Axis labels: 2D ``(Y,X)``, 3D ``(Z,Y,X)``, 4D ``(C,Z,Y,X)``. ``ndim > 4`` raises.
    If ``load_olympus_header`` is true and a companion Olympus ``.txt`` exists, the
    header can be built **without** reading pixels (lazy); loading pixels then
    validates array shape against that header (fail fast on mismatch).

    Args:
        path: Filesystem path to the TIFF.
        header: Optional pre-built header (e.g. from catalog Olympus parse).
        load_olympus_header: When true (default), look for Olympus ``.txt`` next to
            the TIFF on disk. Ignored when ``header`` is provided. Use false for
            streams or to force metadata-only-from-pixeldata behavior.
    """

    def __init__(
        self,
        path: str,
        header: ImageHeader | None = None,
        *,
        load_olympus_header: bool = True,
    ) -> None:
        self._load_olympus_header = load_olympus_header
        super().__init__(path, header)

    @classmethod
    def from_stream(
        cls,
        stream: BinaryIO,
        filename: str,
        header: ImageHeader | None = None,
        *,
        load_olympus_header: bool = False,
    ) -> MyTifImage:
        """Load from a seekable binary stream (``container=None`` path in ``tifffile``).

        Olympus sidecar lookup is disabled by default (no stable on-disk TIFF path).
        """
        inst = object.__new__(cls)
        inst.path = filename
        inst._stream = stream
        inst._img_data = None
        inst._load_olympus_header = load_olympus_header
        if header is None:
            inst._header = inst.read_header()
        else:
            inst._header = header
        return inst

    @classmethod
    def read_header_from_stream(cls, stream: BinaryIO, filename: str) -> ImageHeader:
        """Read TIFF header from a stream without retaining the loader."""
        return cls.from_stream(stream, filename).header

    def read_header(self) -> ImageHeader:
        return self._read_tif_header()

    def _physical_units_for_header(self, scene: Any) -> tuple[tuple[Any, ...], tuple[str, ...]]:
        raise NotImplementedError(
            "MyTifImage does not use _image_header_from_scene; "
            "physical units are set in _read_tif_header via ImageHeader.default_physical_for_dims"
        )

    def _read_tif_array(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.seek(0)
            return np.asarray(tifffile.imread(self._stream))
        return np.asarray(tifffile.imread(self.path))

    def _read_tif_header(self) -> ImageHeader:
        if self._stream is None and self._load_olympus_header:
            odict = read_olympus_txt_dict(self.path)
            if odict is not None:
                try:
                    return image_header_from_olympus_dict(self.path, odict)
                except (ValueError, TypeError, KeyError) as exc:
                    logger.warning(
                        "Olympus txt present but ImageHeader build failed, falling back to pixel read: %s",
                        exc,
                    )
        arr = self._read_tif_array()
        ndim = arr.ndim
        dims = _tif_dims_from_ndim(ndim)
        shape = tuple(int(x) for x in arr.shape)
        sizes = {dims[i]: shape[i] for i in range(ndim)}
        dtype = np.dtype(arr.dtype)
        num_channels = int(sizes["C"]) if "C" in sizes else 1
        physical_units, physical_units_labels = ImageHeader.default_physical_for_dims(dims)
        self._img_data = arr
        return ImageHeader(
            path=self.path,
            shape=shape,
            dims=dims,
            sizes=sizes,
            dtype=dtype,
            num_channels=num_channels,
            num_scenes=1,
            physical_units=physical_units,
            physical_units_labels=physical_units_labels,
            date="",
            time="",
        )

    def _load_full_image_array(self) -> np.ndarray:
        if self._img_data is not None:
            return self._img_data
        arr = self._read_tif_array()
        hdr = self._header
        if hdr is not None:
            expected = tuple(int(x) for x in hdr.shape)
            got = tuple(int(x) for x in arr.shape)
            if expected != got:
                raise ValueError(
                    f"TIFF array shape {got} does not match header shape {expected}"
                )
        return arr


def image_loader_from_upload(
    stream: BinaryIO,
    filename: str,
    header: ImageHeader | None = None,
) -> ImageLoaderBase:
    """Build the appropriate loader from a seekable upload stream and filename.

    Args:
        stream: Seekable binary stream (e.g. :class:`io.BytesIO`); loaders call
            ``seek(0)`` before reading.
        filename: Original name; extension must be ``.oir``, ``.czi``, ``.tif``, or ``.tiff``.
            ``.ome.tif`` / ``.ome.tiff`` are rejected (not routed to :class:`MyTifImage`).
        header: Optional pre-built header.

    Returns:
        :class:`MyOirImage`, :class:`MyCziImage`, or :class:`MyTifImage`.

    Raises:
        ValueError: If the extension is not supported or the file is OME-TIFF.
    """
    ext = Path(filename).suffix.lower()
    if ext == ".oir":
        return MyOirImage.from_stream(stream, filename, header=header)
    if ext == ".czi":
        return MyCziImage.from_stream(stream, filename, header=header)
    if ext in (".tif", ".tiff"):
        lower_base = Path(filename).name.lower()
        if lower_base.endswith(".ome.tif") or lower_base.endswith(".ome.tiff"):
            raise ValueError(
                f"OME-TIFF is not supported by image_loader_from_upload: {filename!r}"
            )
        return MyTifImage.from_stream(
            stream, filename, header=header, load_olympus_header=False
        )
    raise ValueError(
        f"Unsupported file extension {ext!r} for {filename!r}; "
        "expected .oir, .czi, .tif, or .tiff"
    )


if __name__ == "__main__":
    from pprint import pprint

    setup_logging()

    if 1:
        # path = '/Users/cudmore/Sites/kymflow_outer/kymflow/src/kymflow/core/image_loaders/image_loader_plugins/tests/fixtures/czi-samples/disjointedlinescansandframescans'
        path = '/Users/cudmore/Sites/kymflow_outer/kymflow/src/kymflow/core/image_loaders/image_loader_plugins/tests/fixtures/czi-samples/linescansForVelocityMeasurement'
        files = _build_file_list(path, ["czi"])
        for file in files:
            czi_image = MyCziImage(file)
            print("czi_image.header:")
            pprint(czi_image.header.as_dict(), indent=4, width=120, sort_dicts=False)
            czi_image.load_image_data()
            channel = 1
            img_data = czi_image.get_channel_data(channel)
            print(
                f'  channel "{channel}" img_data is: {img_data.shape} {img_data.dtype} min:{img_data.min()} max:{img_data.max()}'
            )

    if 1:
        # path = "/Users/cudmore/Documents/KymFlow/declan_oir_20260409/20251030 WT Male 28d Saline"
        path = '/Users/cudmore/Sites/kymflow_outer/kymflow/src/kymflow/core/image_loaders/image_loader_plugins/tests/fixtures/oir-samples'
        files = sorted(_build_file_list(path, ["oir"]))
        for _idx, file in enumerate(files):
            print(f"=== {_idx}:{len(files)} {file}")
            oir_image = MyOirImage(file)
            pprint(oir_image.header.as_dict(), indent=4, width=120, sort_dicts=False)
            oir_image.load_image_data()
            channel = 0
            img_data = oir_image.get_slice_data(channel)
            print(
                f'  channel "{channel}" img_data is: {img_data.shape} {img_data.dtype} min:{img_data.min()} max:{img_data.max()}'
            )
            if _idx == 3:
                break
