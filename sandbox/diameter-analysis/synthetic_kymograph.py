from __future__ import annotations

from typing import Any

import numpy as np


def generate_synthetic_kymograph(
    n_time: int = 200,
    n_space: int = 128,
    seconds_per_line: float = 0.01,
    um_per_pixel: float = 0.5,
    polarity: str = "bright_on_dark",
    seed: int = 0,
) -> dict[str, Any]:
    """Generate a simple synthetic vessel-like kymograph and edge ground truth."""
    if n_time <= 0 or n_space <= 4:
        raise ValueError("n_time must be > 0 and n_space must be > 4")

    rng = np.random.default_rng(seed)
    t = np.arange(n_time, dtype=float)
    x = np.arange(n_space, dtype=float)

    center = (n_space / 2.0) + 2.5 * np.sin(2.0 * np.pi * t / max(20.0, n_time / 3.0))
    diameter = (n_space * 0.25) + (n_space * 0.06) * np.sin(2.0 * np.pi * t / max(10.0, n_time / 7.0))

    kym = np.empty((n_time, n_space), dtype=float)
    left = center - (diameter / 2.0)
    right = center + (diameter / 2.0)

    for i in range(n_time):
        sigma = max(1.0, diameter[i] / 6.0)
        intensity = np.exp(-((x - center[i]) ** 2) / (2.0 * sigma * sigma))
        kym[i] = intensity

    kym += 0.05 * rng.standard_normal(kym.shape)
    kym -= np.min(kym)
    max_val = np.max(kym)
    if max_val > 0:
        kym /= max_val

    if polarity == "dark_on_bright":
        kym = 1.0 - kym

    return {
        "kymograph": kym,
        "left_edge_px": left,
        "right_edge_px": right,
        "diameter_px": diameter,
        "time_s": t * seconds_per_line,
        "seconds_per_line": float(seconds_per_line),
        "um_per_pixel": float(um_per_pixel),
        "polarity": polarity,
    }
