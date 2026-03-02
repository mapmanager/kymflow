from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile

from diameter_analysis import KymographPayload, Polarity


def load_tiff_kymograph(
    path: str | Path,
    *,
    seconds_per_line: float,
    um_per_pixel: float,
    polarity: str = "bright_on_dark",
) -> KymographPayload:
    in_path = Path(path)
    arr = np.asarray(tifffile.imread(str(in_path)))
    if arr.ndim != 2:
        raise ValueError(
            f"TIFF kymograph must be 2D (time, space); got shape={arr.shape!r}."
        )

    try:
        pol = Polarity(polarity).value
    except ValueError as exc:
        raise ValueError("polarity must be bright_on_dark or dark_on_bright") from exc

    return KymographPayload(
        kymograph=arr,
        seconds_per_line=float(seconds_per_line),
        um_per_pixel=float(um_per_pixel),
        polarity=pol,
        source="tiff",
        path=str(in_path),
    )
