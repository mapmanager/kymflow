from __future__ import annotations

from typing import Any, Optional

import matplotlib.pyplot as plt
import numpy as np


def _result_arrays(results: list[Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    y = np.asarray([r.center_row for r in results], dtype=float)
    t = np.asarray([r.time_s for r in results], dtype=float)
    left = np.asarray([r.left_edge_px for r in results], dtype=float)
    right = np.asarray([r.right_edge_px for r in results], dtype=float)
    return y, t, left, right


def plot_kymograph_with_edges_mpl(
    kymograph: np.ndarray,
    results: list[Any],
    *,
    ax: Optional[plt.Axes] = None,
):
    created = ax is None
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 3.5))
    else:
        fig = ax.figure

    y, _, left, right = _result_arrays(results)

    ax.imshow(kymograph, aspect="auto", origin="lower", cmap="gray")
    ax.plot(left, y, "c-", lw=1, label="left edge")
    ax.plot(right, y, "m-", lw=1, label="right edge")
    ax.legend(loc="upper right")

    ax.set_xlabel("Space (px)")
    ax.set_ylabel("Time index")
    ax.set_title("Kymograph with edges")
    if created:
        fig.tight_layout()
    return fig


def plot_diameter_vs_time_mpl(
    results: list[Any],
    *,
    um_per_pixel: float = 1.0,
    ax: Optional[plt.Axes] = None,
):
    created = ax is None
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 3.2))
    else:
        fig = ax.figure

    _, t, left, right = _result_arrays(results)
    diameter_px = right - left
    diameter_um = diameter_px * um_per_pixel

    ax.plot(t, diameter_um, color="tab:blue", lw=1.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Diameter (um)")
    ax.set_title("Diameter vs time")
    ax.grid(alpha=0.3)
    if created:
        fig.tight_layout()
    return fig


def plot_kymograph_with_edges_plotly_dict(
    kymograph: np.ndarray,
    results: list[Any],
) -> dict[str, Any]:
    y, _, left, right = _result_arrays(results)
    return {
        "data": [
            {
                "type": "heatmap",
                "z": np.asarray(kymograph).tolist(),
                "colorscale": "Gray",
                "showscale": True,
                "name": "kymograph",
            },
            {
                "type": "scatter",
                "x": left.tolist(),
                "y": y.tolist(),
                "mode": "lines",
                "name": "left edge",
                "line": {"color": "cyan"},
            },
            {
                "type": "scatter",
                "x": right.tolist(),
                "y": y.tolist(),
                "mode": "lines",
                "name": "right edge",
                "line": {"color": "magenta"},
            },
        ],
        "layout": {
            "title": "Kymograph with edges",
            "xaxis": {"title": "Space (px)"},
            "yaxis": {"title": "Time index"},
        },
    }


def plot_diameter_vs_time_plotly_dict(
    results: list[Any],
    *,
    um_per_pixel: float = 1.0,
) -> dict[str, Any]:
    _, t, left, right = _result_arrays(results)
    diameter_um = (right - left) * um_per_pixel
    return {
        "data": [
            {
                "type": "scatter",
                "mode": "lines",
                "x": t.tolist(),
                "y": diameter_um.tolist(),
                "name": "diameter_um",
                "line": {"color": "royalblue"},
            }
        ],
        "layout": {
            "title": "Diameter vs time",
            "xaxis": {"title": "Time (s)"},
            "yaxis": {"title": "Diameter (um)"},
        },
    }
