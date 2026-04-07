import os
from pathlib import Path
from typing import Any, Optional

import numpy as np
import matplotlib.pyplot as plt

import czifile


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

def read_czi_header(path: str) -> dict[str, Any]:
    """Return a minimal header from the first scene of a CZI file.

    Args:
        path: Full path to a CZI file.

    Returns:
        Dict with shape, dims, sizes, dtype, num_channels, and num_scenes.
    """
    with czifile.CziFile(path) as czi_file:
        scenes = czi_file.scenes
        num_scenes = len(scenes)  # usually just 1 scene

        scene = scenes[0]
        shape = tuple(scene.shape)
        dims = tuple(scene.dims)
        sizes = dict(scene.sizes)
        dtype = scene.dtype

        if "C" in sizes:
            num_channels = int(sizes["C"])
        else:
            num_channels = 1

        # physical units
        xarr = scene.asxarray()
        print(f'xarr.name:{xarr.name}')
        print(f'xarr.sizes:{xarr.sizes}')
        print(f'xarr.coords: { type(xarr.coords)}')
        # print(f'{xarr.coords}')
        # print(f'xarr.coords["T"]: {xarr.coords["T"][0]} {xarr.coords["T"][1]} {xarr.coords["T"][2]}')
        # print(f'xarr.coords["X"]: {xarr.coords["X"][0]} {xarr.coords["X"][1]} {xarr.coords["X"][2]}')

        seconds_per_line = float((xarr.coords['T'][1] - xarr.coords['T'][0]).item())
        _meters_per_pixel = float((xarr.coords['X'][1] - xarr.coords['X'][0]).item())
        um_per_pixel = _meters_per_pixel * 1e6
        # print(f'xarr.coords["Y"].size: {xarr.coords["X"].size}')

        return {
            "shape": shape,
            "dims": dims,
            "sizes": sizes,
            "dtype": dtype,
            "num_channels": num_channels,
            "num_scenes": num_scenes,
            "seconds_per_line": seconds_per_line,
            "um_per_pixel": um_per_pixel,
        }

def show_img_transposed_auto(img: np.ndarray) -> None:
    """Show 2D uint8 image with aggressive auto contrast."""
    if img.ndim != 2:
        raise ValueError(f"Expected 2D array, got shape {img.shape}")

    img_t = img.T

    # robust contrast (ignore extreme outliers)
    vmin = np.percentile(img_t, 1)
    vmax = np.percentile(img_t, 99)

    if vmin == vmax:
        vmin = img_t.min()
        vmax = img_t.max()
        if vmin == vmax:
            vmax = vmin + 1

    # print(f"imshow vmin={vmin}, vmax={vmax}")

    plt.figure()
    plt.imshow(img_t, cmap="gray", origin="lower", vmin=vmin, vmax=vmax, aspect="auto")
    plt.colorbar()
    plt.tight_layout()
    plt.show()


import pprint
import czifile


def probe_czi_line_metadata(path: str, max_entries: int = 20) -> None:
    """Probe low-level czifile metadata for line-scan boundary clues.

    Args:
        path: Full path to a CZI file.
        max_entries: Maximum number of directory entries to inspect.
    """
    print(f'probe_czi_line_metadata for {path}')
    
    with czifile.CziFile(path) as czi_file:
        img = czi_file.scenes[0]

        print(f"path: {path}")
        print(f"scene shape: {img.shape}")
        print(f"scene dims: {img.dims}")
        print(f"scene sizes: {img.sizes}")
        print(f"scene dtype: {img.dtype}")
        print(f"scene bbox: {img.bbox}")
        print(f"num directory_entries: {len(img.directory_entries)}")
        print()

        for i, entry in enumerate(img.directory_entries[:max_entries]):
            print(f"--- entry {i} ---")
            print(f"entry.dims: {entry.dims}")
            print(f"entry.start: {entry.start}")
            print(f"entry.shape: {entry.shape}")
            print(f"entry.stored_shape: {entry.stored_shape}")

            # Optional fields that may or may not exist depending on file/entry type.
            for attr_name in (
                "mosaic_index",
                "pyramid_type",
                "file_position",
                "compression",
            ):
                if hasattr(entry, attr_name):
                    try:
                        print(f"entry.{attr_name}: {getattr(entry, attr_name)}")
                    except Exception as e:
                        print(f"entry.{attr_name}: <error: {e}>")

            try:
                segdata = entry.read_segment_data(czi_file)
            except Exception as e:
                print(f"read_segment_data error: {e}")
                print()
                continue

            try:
                metadata = segdata.metadata(asdict=True)
            except Exception as e:
                print(f"segdata.metadata error: {e}")
                print()
                continue

            print("subblock metadata:")
            pprint.pprint(metadata, width=120, sort_dicts=False)
            print()

def load_czi_img_data(path: str) -> Optional[np.ndarray]:
    """Load normalized kymograph-style image data from the first CZI scene.

    Accepted scene dims:
        - ('C', 'T', 'X'): returned as (C, Y, X), where T is interpreted as Y
        - ('C', 'X'): expanded to (C, 1, X)

    Rejected scene dims:
        - ('C', 'Y', 'X')
        - ('C', 'T', 'Y', 'X')
        - anything else

    Args:
        path: Full path to a CZI file.

    Returns:
        Numpy array with shape (C, Y, X) for supported kymograph-like data,
        otherwise None.
    """
    with czifile.CziFile(path) as czi_file:
        scene = czi_file.scenes[0]
        dims = tuple(scene.dims)

        if dims == ("C", "T", "X"):
            arr = scene.asarray()
            return arr if arr.ndim == 3 else None

        # if dims == ("C", "X"):
        #     arr = scene.asarray()
        #     if arr.ndim != 2:
        #         return None
        #     return np.expand_dims(arr, axis=1)

        print(f'error: return None for {dims}')
        return None

def open_one_file(path:str) -> dict:
    # with czifile.CziFile(path) as czi_file:
    if 1:
        header = read_czi_header(path)
        print(f'header:{header}')

        img_data = load_czi_img_data(path)
        if img_data is not None:
            print(f'img_data shape:{img_data.shape}')
            print(f'img_data dtype:{img_data.dtype}')
            print(f'img_data min:{img_data.min()}')
            print(f'img_data max:{img_data.max()}')

        # if file is `Image 17.czi`, then
        # if 'Image 17.czi' in path:
        #     # probe_czi_line_metadata(path, max_entries=20)

        #     channel = 1
        #     show_img_transposed_auto(img_data[channel, :, :])

if __name__ == '__main__':
    path = '/Users/cudmore/Dropbox/data/sanpy-users/kym-users/czi-data/disjointedlinescansandframescans'
    # path = '/Users/cudmore/Dropbox/data/sanpy-users/kym-users/czi-data/linescansForVelocityMeasurement'

    files = _build_file_list(path, ['czi'])
    
    files = ['/Users/cudmore/Dropbox/data/sanpy-users/kym-users/czi-data/disjointedlinescansandframescans/Image 17.czi']

    for file in files:
        print(file)
        open_one_file(file)