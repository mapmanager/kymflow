from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional
from dataclasses import asdict, dataclass
from datetime import datetime

import numpy as np
import oirfile

logger = logging.getLogger(__name__)

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
class OirHeader:
    """Small metadata container for an OIR image file.

    Attributes:
        path: Full path to the source OIR file.
        date_time: Original datetime string from OIR metadata, if available.
        date: Date formatted as YYYYMMDD, if parsing succeeded.
        time: Time formatted as HH:MM:SS.ms, if parsing succeeded.
        num_channels: Number of channels in the normalized (C, Y, X) image.
        shape: Normalized image shape as (C, Y, X), or None if unsupported.
        dims_raw: Raw OIR dims returned by the reader.
        shape_raw: Raw array shape returned by the reader.
        dtype: Numpy dtype name of the loaded image data.
        is_supported: True when dims matched the strict supported contract.
        error: Human-readable reason when the file is unsupported.
    """

    path: str
    # date_time: Optional[str]
    date: Optional[str]
    time: Optional[str]
    num_channels: Optional[int]
    shape: Optional[tuple[int, int, int]]
    # dims_raw: tuple[str, ...]
    # shape_raw: tuple[int, ...]
    dtype: str
    is_supported: bool
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Return all dataclass fields as a dictionary."""
        return asdict(self)

def _normalize_to_cyx_singleton_extras(
    img_data: np.ndarray,
    dims: tuple[str, ...],
) -> Optional[np.ndarray]:
    """Normalize OIR image data to (C, Y, X) with singleton-only extra axes.

    Rules:
        - Y and X must exist.
        - C is optional; if missing, a singleton channel axis is inserted.
        - Any non-(C,Y,X) axis is accepted only when its size is 1 and is
          dropped by taking index 0.
        - Any non-(C,Y,X) axis with size > 1 is rejected (no guessing).

    Args:
        img_data: Raw numpy array loaded from the OIR file.
        dims: Dimension labels corresponding to `img_data`.

    Returns:
        A numpy array with shape (C, Y, X) when supported, otherwise None.
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


def _parse_oir_datetime(
    date_time_str: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Parse an OIR datetime string into YYYYMMDD and HH:MM:SS.ms strings.

    This function is intentionally conservative:
    it preserves the original datetime string separately and only fills `date`
    and `time` if parsing succeeds.

    Args:
        date_time_str: Raw datetime string from OIR metadata.

    Returns:
        A tuple of:
            - date formatted as YYYYMMDD, or None
            - time formatted as HH:MM:SS.ms, or None
    """
    if not date_time_str:
        return None, None

    raw = date_time_str.strip()

    # Try a few safe normalizations before parsing.
    candidates = [
        raw,
        raw.replace("Z", "+00:00"),
    ]

    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            return dt.strftime("%Y%m%d"), dt.strftime("%H:%M:%S.%f")[:-3]
        except ValueError:
            continue

    logger.warning("Could not parse OIR datetime string: %r", date_time_str)
    return None, None


def read_oir_header(path: str) -> OirHeader:
    """Read a small normalized header from an OIR file.

    This function opens an OIR file, inspects metadata and dims, loads the raw
    image array, and attempts to normalize it to (C, Y, X).

    Supported dims:
        - ('C', 'Y', 'X')
        - ('Y', 'X')
        - Plus dims with extra singleton axes (e.g., T=1, Z=1), such as
          ('T', 'Y', 'X') or ('T', 'C', 'Y', 'X') when T==1.

    For unsupported files, the function does not raise for dims mismatch.
    Instead, it returns an `OirHeader` with:
        - `is_supported=False`
        - `shape=None`
        - `num_channels=None`
        - `error` populated

    Args:
        path: Full path to the OIR file.

    Returns:
        An `OirHeader` dataclass with parsed metadata and normalized shape info.
    """
    path_obj = Path(path)

    with oirfile.OirFile(path_obj) as oir:
        attrs = oir.attrs
        dims_raw = tuple(oir.dims)
        img_data = oir.asarray()

    date_time_str = attrs.get("datetime")
    date_str, time_str = _parse_oir_datetime(date_time_str)

    shape_raw = tuple(int(x) for x in img_data.shape)
    dtype_name = str(img_data.dtype)

    cyx_data = _normalize_to_cyx_singleton_extras(img_data, dims_raw)

    if cyx_data is None:
        error = (
            f"Unsupported dims {dims_raw} with shape {shape_raw}; expected CYX-compatible dims with only singleton extras"
        )
        # logger.error("%s for file: %s", error, path_obj)
        return OirHeader(
            path=str(path_obj),
            # date_time=date_time_str,
            date=date_str,
            time=time_str,
            num_channels=None,
            shape=None,
            # dims_raw=dims_raw,
            # shape_raw=shape_raw,
            dtype=dtype_name,
            is_supported=False,
            error=error,
        )

    final_shape = tuple(int(x) for x in cyx_data.shape)

    return OirHeader(
        path=str(path_obj),
        # date_time=date_time_str,
        date=date_str,
        time=time_str,
        num_channels=int(final_shape[0]),
        shape=final_shape,
        # dims_raw=dims_raw,
        # shape_raw=shape_raw,
        dtype=dtype_name,
        is_supported=True,
        error=None,
    )
   
if __name__ == "__main__":
    from pprint import pprint

    path = '/Users/cudmore/Dropbox/data/declan/20221216 WT Female Open Craniotomy'
    
    """
    (1000, 512, 512) ('T', 'Y', 'X') /Users/cudmore/Dropbox/data/cudmore-fiji-plugins/test-data/example-oir/20190416__0001.oir
    (7, 2, 512, 512) ('T', 'C', 'Y', 'X') /Users/cudmore/Dropbox/data/cudmore-fiji-plugins/test-data/example-oir/20190429_tst2_0009.oir
    (2, 5200, 32) ('C', 'Y', 'X') /Users/cudmore/Dropbox/data/cudmore-fiji-plugins/test-data/example-oir/20190429_tst2_0011.oir
    """
    # path = '/Users/cudmore/Dropbox/data/cudmore-fiji-plugins/test-data'
    
    path = '/Users/cudmore/Dropbox/data/arsalan'

    files = _build_file_list(path, ['oir', 'tif'])
    
    for file in files:
        if file.endswith('.oir'):
            # load_oir_v2(file)
            oir_header = read_oir_header(file)
            if oir_header.is_supported:
                pprint(oir_header.to_dict(), indent=4, width=220, sort_dicts=False)
        else:
            # print(f'  {file} is not an oir file')
            pass
