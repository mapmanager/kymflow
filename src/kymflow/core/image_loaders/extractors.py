# path: extractors.py
from __future__ import annotations

import re
from typing import Optional

_INT_RE = re.compile(r"[-+]?\d+")
_FLOAT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")

def extract_int(s: str | None) -> int | None:
    if not s:
        return None
    m = _INT_RE.search(s)
    return int(m.group()) if m else None

def extract_float(s: str | None) -> float | None:
    if not s:
        return None
    m = _FLOAT_RE.search(s)
    return float(m.group()) if m else None

def extract_image_size_pixels(s: str | None) -> tuple[int, int] | None:
    """
    "38 * 30000 [pixel]" -> (38, 30000)
    """
    if not s:
        return None
    # grab first two ints in the string
    nums = _INT_RE.findall(s)
    if len(nums) < 2:
        return None
    return int(nums[0]), int(nums[1])

def extract_um_per_pixel_from_x_dimension(s: str | None) -> float | None:
    """
    "416, 0.0 - 172.357 [um], 0.414 [um/pixel]" -> 0.414
    More robust than split()[7] because it searches for the um/pixel chunk.
    """
    if not s:
        return None
    # split by commas, find the part mentioning um/pixel
    parts = [p.strip() for p in s.split(",")]
    for p in parts:
        if "um/pixel" in p:
            return extract_float(p)
    # fallback: last float in the string (often the um/pixel)
    floats = _FLOAT_RE.findall(s)
    return float(floats[-1]) if floats else None

def extract_duration_sec_from_t_dimension(s: str | None) -> float | None:
    """
    "1, 0.000 - 35.099 [s], Interval FreeRun" -> 35.099
    Strategy: find the segment containing "[s]" and take the *last* float in it.
    """
    if not s:
        return None
    parts = [p.strip() for p in s.split(",")]
    for p in parts:
        if "[s]" in p:
            floats = _FLOAT_RE.findall(p)
            return float(floats[-1]) if floats else None
    # fallback: last float in whole string
    floats = _FLOAT_RE.findall(s)
    return float(floats[-1]) if floats else None
