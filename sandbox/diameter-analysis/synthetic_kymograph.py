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
    noise_sigma: float = 0.02,
) -> dict[str, Any]:
    """Generate a deterministic synthetic vessel-like kymograph with truth diameter.

    `truth['truth_diameter_px']` is aligned to time rows.
    """
    if n_time <= 0 or n_space <= 8:
        raise ValueError("n_time must be > 0 and n_space must be > 8")

    rng = np.random.default_rng(seed)
    t = np.arange(n_time, dtype=float)
    x = np.arange(n_space, dtype=float)

    center = (n_space / 2.0) + 3.0 * np.sin(2.0 * np.pi * t / max(25.0, n_time / 4.0))
    diameter = (n_space * 0.28) + (n_space * 0.07) * np.sin(
        2.0 * np.pi * t / max(12.0, n_time / 8.0)
    )
    diameter = np.clip(diameter, 8.0, n_space * 0.6)

    left = center - (diameter / 2.0)
    right = center + (diameter / 2.0)

    kym = np.empty((n_time, n_space), dtype=float)
    edge_softness = 1.5
    for i in range(n_time):
        left_sigmoid = 1.0 / (1.0 + np.exp(-(x - left[i]) / edge_softness))
        right_sigmoid = 1.0 / (1.0 + np.exp((x - right[i]) / edge_softness))
        profile = left_sigmoid * right_sigmoid
        kym[i] = profile

    if noise_sigma > 0:
        kym += noise_sigma * rng.standard_normal(kym.shape)

    kym -= np.min(kym)
    kmax = np.max(kym)
    if kmax > 0:
        kym /= kmax

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
        "truth": {
            "truth_diameter_px": diameter.copy(),
            "truth_left_edge_px": left.copy(),
            "truth_right_edge_px": right.copy(),
        },
    }
