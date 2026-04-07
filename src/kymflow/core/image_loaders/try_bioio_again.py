from bioio import BioImage
from pathlib import Path
import os
from typing import Any
import numpy as np
import matplotlib.pyplot as plt




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

    print(f"imshow vmin={vmin}, vmax={vmax}")

    plt.figure()
    plt.imshow(img_t, cmap="gray", origin="lower", vmin=vmin, vmax=vmax, aspect="auto")
    plt.colorbar()
    plt.tight_layout()
    plt.show()

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


def read_czi_basic_header(path: str) -> dict[str, Any]:
    """Return a minimal header from a CZI file using BioImage.

    This function is intentionally metadata-only. It does not trigger pixel
    loading, Dask computation, plotting, or low-level CZI geometry inspection.

    Returned values reflect the BioImage standardized view of the file.

    Args:
        path: Full path to a CZI file.

    Returns:
        Dict with:
            - dtype: BioImage pixel dtype
            - shape: Tuple of axis sizes matching `dims`
            - dims: Tuple of dimension labels
            - num_channels: Number of channels if 'C' exists, otherwise 1
    """
    # img = BioImage(path)
    # img = BioImage(path, use_aicspylibczi=True)
    img = BioImage(path, reconstruct_mosaic=False)

    # BioImage exposes standardized dims and shape without forcing a full pixel load.
    dims = tuple(img.dims.order)
    shape = tuple(img.shape)
    dtype = img.dtype

    # Determine channel count from the standardized dims/shape contract.
    if "C" in dims:
        channel_axis = dims.index("C")
        num_channels = int(shape[channel_axis])
    else:
        num_channels = 1

    return {
        "dtype": dtype,
        "shape": shape,
        "dims": dims,
        "num_channels": num_channels,
    }

if __name__ == '__main__':
    from pprint import pprint

    path = '/Users/cudmore/Dropbox/data/sanpy-users/kym-users/czi-data/disjointedlinescansandframescans'
    # seems the only good file here is:
    #  /Users/cudmore/Dropbox/data/sanpy-users/kym-users/czi-data/disjointedlinescansandframescans/Image 19.czi
    # {'shape': (1, 2, 1, 11672, 6144), 'dims': ('T', 'C', 'Z', 'Y', 'X'), 'num_channels': 2}
    #  

    # path = '/Users/cudmore/Dropbox/data/sanpy-users/kym-users/czi-data/linescansForVelocityMeasurement'
    # this has no useful files, they all come up like this:
    # {'shape': (1, 2, 1, 1, 512), 'dims': ('T', 'C', 'Z', 'Y', 'X'), 'num_channels': 2}

    path = '/Users/cudmore/Dropbox/data/sanpy-users/kym-users/plesnila'

    files = _build_file_list(path, ['czi'])
    
    # files = ['/Users/cudmore/Dropbox/data/sanpy-users/kym-users/czi-data/disjointedlinescansandframescans/Image 19.czi']
    files = ['/Users/cudmore/Dropbox/data/sanpy-users/kym-users/plesnila/test-fiji/Image 11.czi']

    for file in files:
        print(f'=== {file}')
    
        header = read_czi_basic_header(file)
        pprint(header, indent=4, width=120, sort_dicts=False)

        # break