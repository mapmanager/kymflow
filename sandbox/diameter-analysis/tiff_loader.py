from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import tifffile

from diameter_analysis import KymographPayload, Polarity

logger = logging.getLogger(__name__)


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

    loaded_min = float(np.nanmin(arr))
    loaded_max = float(np.nanmax(arr))
    logger.info(
        "Loaded TIFF path=%s shape=%s dtype=%s min=%s max=%s",
        str(in_path),
        arr.shape,
        str(arr.dtype),
        loaded_min,
        loaded_max,
    )

    return KymographPayload(
        kymograph=arr,
        seconds_per_line=float(seconds_per_line),
        um_per_pixel=float(um_per_pixel),
        polarity=pol,
        source="tiff",
        path=str(in_path),
        loaded_shape=(int(arr.shape[0]), int(arr.shape[1])),
        loaded_dtype=str(arr.dtype),
        loaded_min=loaded_min,
        loaded_max=loaded_max,
    )
