from __future__ import annotations

from typing import Any, Optional

import matplotlib.pyplot as plt
import numpy as np


def plot_kymograph_with_edges_mpl(
    kymograph: np.ndarray,
    left_edge_px: Optional[np.ndarray] = None,
    right_edge_px: Optional[np.ndarray] = None,
):
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.imshow(kymograph, aspect="auto", origin="lower", cmap="gray")

    if left_edge_px is not None:
        ax.plot(left_edge_px, np.arange(len(left_edge_px)), "c-", lw=1, label="left edge")
    if right_edge_px is not None:
        ax.plot(right_edge_px, np.arange(len(right_edge_px)), "m-", lw=1, label="right edge")
    if left_edge_px is not None or right_edge_px is not None:
        ax.legend(loc="upper right")

    ax.set_xlabel("Space (px)")
    ax.set_ylabel("Time index")
    ax.set_title("Kymograph with edges")
    fig.tight_layout()
    return fig


def plot_diameter_vs_time_mpl(time_s: np.ndarray, diameter: np.ndarray, ylabel: str = "Diameter"):
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.plot(time_s, diameter, color="tab:blue", lw=1.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(ylabel)
    ax.set_title("Diameter vs time")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def plot_kymograph_with_edges_plotly_dict(
    kymograph: np.ndarray,
    left_edge_px: Optional[np.ndarray] = None,
    right_edge_px: Optional[np.ndarray] = None,
) -> dict[str, Any]:
    data = [
        {
            "type": "heatmap",
            "z": np.asarray(kymograph).tolist(),
            "colorscale": "Gray",
            "showscale": True,
            "name": "kymograph",
        }
    ]

    if left_edge_px is not None:
        data.append(
            {
                "type": "scatter",
                "x": np.asarray(left_edge_px).tolist(),
                "y": np.arange(len(left_edge_px)).tolist(),
                "mode": "lines",
                "name": "left edge",
                "line": {"color": "cyan"},
            }
        )
    if right_edge_px is not None:
        data.append(
            {
                "type": "scatter",
                "x": np.asarray(right_edge_px).tolist(),
                "y": np.arange(len(right_edge_px)).tolist(),
                "mode": "lines",
                "name": "right edge",
                "line": {"color": "magenta"},
            }
        )

    layout = {
        "title": "Kymograph with edges",
        "xaxis": {"title": "Space (px)"},
        "yaxis": {"title": "Time index"},
    }
    return {"data": data, "layout": layout}


def plot_diameter_vs_time_plotly_dict(
    time_s: np.ndarray,
    diameter: np.ndarray,
    ylabel: str = "Diameter",
) -> dict[str, Any]:
    return {
        "data": [
            {
                "type": "scatter",
                "mode": "lines",
                "x": np.asarray(time_s).tolist(),
                "y": np.asarray(diameter).tolist(),
                "name": "diameter",
                "line": {"color": "royalblue"},
            }
        ],
        "layout": {
            "title": "Diameter vs time",
            "xaxis": {"title": "Time (s)"},
            "yaxis": {"title": ylabel},
        },
    }
