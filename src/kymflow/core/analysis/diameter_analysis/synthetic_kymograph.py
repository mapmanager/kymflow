from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from serialization import dataclass_from_dict, dataclass_to_dict


OutputDType = Literal["float32", "float64", "uint16"]
PolarityType = Literal["bright_on_dark", "dark_on_bright"]


@dataclass(frozen=True)
class SyntheticKymographParams:
    n_time: int = 200
    n_space: int = 128
    seconds_per_line: float = 0.01
    um_per_pixel: float = 0.5
    polarity: PolarityType = "bright_on_dark"
    seed: int = 0

    output_dtype: OutputDType = "float64"
    effective_bits: int = 11
    baseline_counts: float = 0.0
    signal_peak_counts: float = 2047.0
    clip: bool = True

    bg_gaussian_sigma_counts: float = 0.0
    bg_gaussian_sigma_frac: float | None = 0.02
    bg_drift_amp_counts: float = 0.0
    bg_drift_period_lines: int = 120
    fixed_pattern_col_sigma_counts: float = 0.0

    speckle_sigma_frac: float = 0.0
    wall_jitter_px: float = 0.0

    bright_band_enabled: bool = False
    bright_band_x_center_px: int = 96
    bright_band_width_px: int = 6
    bright_band_amplitude_counts: float = 0.0
    bright_band_saturate: bool = False

    @property
    def max_counts(self) -> float:
        return float((2**int(self.effective_bits)) - 1)

    def to_dict(self) -> dict[str, Any]:
        out = dataclass_to_dict(self)
        out["max_counts"] = float(self.max_counts)
        return out

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SyntheticKymographParams":
        return dataclass_from_dict(cls, payload)


def _validate_params(params: SyntheticKymographParams) -> None:
    if params.n_time <= 0 or params.n_space <= 8:
        raise ValueError("n_time must be > 0 and n_space must be > 8")
    if params.output_dtype not in {"float32", "float64", "uint16"}:
        raise ValueError("output_dtype must be one of: float32, float64, uint16")
    if params.effective_bits < 1 or params.effective_bits > 16:
        raise ValueError("effective_bits must be in [1,16]")
    if params.signal_peak_counts <= 0:
        raise ValueError("signal_peak_counts must be > 0")
    if params.bg_drift_period_lines <= 0:
        raise ValueError("bg_drift_period_lines must be > 0")
    if params.bright_band_width_px < 1:
        raise ValueError("bright_band_width_px must be >= 1")
    if params.polarity not in {"bright_on_dark", "dark_on_bright"}:
        raise ValueError("polarity must be bright_on_dark or dark_on_bright")


# Backward-compatible signature plus preferred `synthetic_params` object.
def generate_synthetic_kymograph(
    n_time: int = 200,
    n_space: int = 128,
    seconds_per_line: float = 0.01,
    um_per_pixel: float = 0.5,
    polarity: str = "bright_on_dark",
    seed: int = 0,
    noise_sigma: float = 0.02,
    synthetic_params: SyntheticKymographParams | None = None,
) -> dict[str, Any]:
    """Generate deterministic synthetic kymograph data with optional noise/quantization realism.

    `baseline_counts` is a constant offset everywhere (camera/autofluorescence).
    `signal_peak_counts` is target signal amplitude above baseline in counts.

    Noise/artifact order:
    1) baseline offset
    2) background drift
    3) fixed pattern (per-column)
    4) additive gaussian
    5) speckle on signal
    6) bright band additive artifact (+ optional saturate)
    7) final clipping and dtype conversion
    """
    params = synthetic_params or SyntheticKymographParams(
        n_time=n_time,
        n_space=n_space,
        seconds_per_line=seconds_per_line,
        um_per_pixel=um_per_pixel,
        polarity=polarity,
        seed=seed,
        bg_gaussian_sigma_frac=noise_sigma,
    )
    _validate_params(params)

    rng = np.random.default_rng(params.seed)
    t = np.arange(params.n_time, dtype=float)
    x = np.arange(params.n_space, dtype=float)

    center = (params.n_space / 2.0) + 3.0 * np.sin(
        2.0 * np.pi * t / max(25.0, params.n_time / 4.0)
    )
    diameter_base = (params.n_space * 0.28) + (params.n_space * 0.07) * np.sin(
        2.0 * np.pi * t / max(12.0, params.n_time / 8.0)
    )
    diameter_base = np.clip(diameter_base, 8.0, params.n_space * 0.6)

    if params.wall_jitter_px > 0:
        left_jitter = rng.normal(0.0, params.wall_jitter_px, size=params.n_time)
        right_jitter = rng.normal(0.0, params.wall_jitter_px, size=params.n_time)
    else:
        left_jitter = np.zeros(params.n_time, dtype=float)
        right_jitter = np.zeros(params.n_time, dtype=float)

    left = center - (diameter_base / 2.0) + left_jitter
    right = center + (diameter_base / 2.0) + right_jitter
    right = np.maximum(right, left + 1.0)
    diameter = right - left

    signal = np.empty((params.n_time, params.n_space), dtype=float)
    edge_softness = 1.5
    for i in range(params.n_time):
        left_sigmoid = 1.0 / (1.0 + np.exp(-(x - left[i]) / edge_softness))
        right_sigmoid = 1.0 / (1.0 + np.exp((x - right[i]) / edge_softness))
        signal[i] = left_sigmoid * right_sigmoid

    max_counts = params.max_counts

    image_counts = signal * params.signal_peak_counts
    image_counts += params.baseline_counts

    if params.bg_drift_amp_counts != 0:
        drift = params.bg_drift_amp_counts * np.sin(
            2.0 * np.pi * t / float(params.bg_drift_period_lines)
        )
        image_counts += drift[:, None]

    if params.fixed_pattern_col_sigma_counts > 0:
        col_pattern = rng.normal(0.0, params.fixed_pattern_col_sigma_counts, size=params.n_space)
        image_counts += col_pattern[None, :]

    sigma_add_counts = params.bg_gaussian_sigma_counts
    if params.bg_gaussian_sigma_frac is not None:
        sigma_add_counts += params.bg_gaussian_sigma_frac * params.signal_peak_counts
    if sigma_add_counts > 0:
        image_counts += rng.normal(0.0, sigma_add_counts, size=image_counts.shape)

    if params.speckle_sigma_frac > 0:
        image_counts += signal * params.signal_peak_counts * rng.normal(
            0.0, params.speckle_sigma_frac, size=image_counts.shape
        )

    if params.bright_band_enabled:
        width = max(1, int(params.bright_band_width_px))
        half = width // 2
        c = int(np.clip(params.bright_band_x_center_px, 0, params.n_space - 1))
        x0 = max(0, c - half)
        x1 = min(params.n_space, c + half + (0 if width % 2 == 0 else 1))
        image_counts[:, x0:x1] += params.bright_band_amplitude_counts

    if params.polarity == "dark_on_bright":
        pivot = params.baseline_counts + params.signal_peak_counts
        image_counts = (2.0 * params.baseline_counts + params.signal_peak_counts) - image_counts

    if params.clip:
        image_counts = np.clip(image_counts, 0.0, max_counts)

    if params.bright_band_enabled and params.bright_band_saturate and params.clip:
        width = max(1, int(params.bright_band_width_px))
        half = width // 2
        c = int(np.clip(params.bright_band_x_center_px, 0, params.n_space - 1))
        x0 = max(0, c - half)
        x1 = min(params.n_space, c + half + (0 if width % 2 == 0 else 1))
        image_counts[:, x0:x1] = max_counts

    if params.output_dtype == "uint16":
        kymograph = image_counts.astype(np.uint16)
    elif params.output_dtype == "float32":
        kymograph = (image_counts / max_counts).astype(np.float32)
    else:
        kymograph = (image_counts / max_counts).astype(np.float64)

    return {
        "kymograph": kymograph,
        "left_edge_px": left,
        "right_edge_px": right,
        "diameter_px": diameter,
        "time_s": t * params.seconds_per_line,
        "seconds_per_line": float(params.seconds_per_line),
        "um_per_pixel": float(params.um_per_pixel),
        "polarity": params.polarity,
        "meta": {
            "seconds_per_line": float(params.seconds_per_line),
            "um_per_pixel": float(params.um_per_pixel),
            "polarity": params.polarity,
        },
        "truth": {
            "truth_diameter_px": diameter.copy(),
            "truth_left_edge_px": left.copy(),
            "truth_right_edge_px": right.copy(),
        },
        "synthetic_params": params.to_dict(),
    }
