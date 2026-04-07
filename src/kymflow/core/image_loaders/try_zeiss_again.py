from __future__ import annotations

from pathlib import Path
import os
from typing import Any

import numpy as np
from pylibCZIrw import czi

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

def read_czi_probe(path: str) -> dict[str, Any]:
    """Probe a CZI file: header + per-channel stats at T=0, Z=0."""

    # file_path = Path(path)

    with czi.open_czi(path) as f:
        bbox = f.total_bounding_box
        total_rect = f.total_bounding_rectangle
        scene_rects = f.scenes_bounding_rectangle
        pixel_types = f.pixel_types

        c_start, c_stop = bbox["C"]
        num_channels = int(c_stop - c_start)

        results = []

        for c_idx in range(c_start, c_stop):
            plane = {
                "C": int(c_idx),
                "T": int(bbox["T"][0]),
                "Z": int(bbox["Z"][0]),
                "B": int(bbox.get("B", (0, 1))[0]),
                "V": int(bbox.get("V", (0, 1))[0]),
            }

            try:
                data = f.read(plane=plane)
                data = np.asarray(data)

                results.append({
                    "channel": c_idx,
                    "shape": tuple(data.shape),
                    "dtype": data.dtype,
                    "min": int(data.min()),
                    "max": int(data.max()),
                })

            except Exception as e:
                results.append({
                    "channel": c_idx,
                    "error": str(e),
                })

    return {
        "path": str(path),
        "bbox": bbox,
        "total_rect": total_rect,
        "scene_rects": scene_rects,
        "pixel_types": pixel_types,
        "num_channels": num_channels,
        "per_channel": results,
    }

if __name__ == '__main__':
    from pprint import pprint

    path = '/Users/cudmore/Dropbox/data/sanpy-users/kym-users/czi-data/disjointedlinescansandframescans'

    files = _build_file_list(path, ['czi'])

    for file in files:
        probe = read_czi_probe(file)
        pprint(probe, indent=4, width=120, sort_dicts=False)