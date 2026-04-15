from __future__ import annotations

from typing import Any, Optional

# import matplotlib.pyplot as plt
import numpy as np


def _result_arrays(
    results: list[Any],
    *,
    seconds_per_line: Optional[float],
    um_per_pixel: Optional[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    center_rows = np.asarray([r.center_row for r in results], dtype=float)
    time_s = np.asarray([r.time_s for r in results], dtype=float)
    left_px = np.asarray([r.left_edge_px for r in results], dtype=float)
    right_px = np.asarray([r.right_edge_px for r in results], dtype=float)

    x_time = time_s if seconds_per_line is not None else center_rows
    if um_per_pixel is not None:
        left_space = left_px * um_per_pixel
        right_space = right_px * um_per_pixel
    else:
        left_space = left_px
        right_space = right_px
    return x_time, time_s, left_space, right_space


def _display_axes(
    kymograph: np.ndarray,
    *,
    seconds_per_line: Optional[float],
    um_per_pixel: Optional[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, str, str]:
    arr = np.asarray(kymograph, dtype=float)
    if arr.ndim != 2:
        raise ValueError("kymograph must be 2D (time, space)")

    img_disp = arr.transpose()

    n_time, n_space = arr.shape
    if seconds_per_line is not None:
        x = np.arange(n_time, dtype=float) * seconds_per_line
        xlabel = "time (s)"
    else:
        x = np.arange(n_time, dtype=float)
        xlabel = "time (rows)"

    if um_per_pixel is not None:
        y = np.arange(n_space, dtype=float) * um_per_pixel
        ylabel = "space (um)"
    else:
        y = np.arange(n_space, dtype=float)
        ylabel = "space (px)"

    return img_disp, x, y, xlabel, ylabel


def plot_kymograph_with_edges_mpl(
    kymograph: np.ndarray,
    results: list[Any],
    *,
    seconds_per_line: Optional[float] = None,
    um_per_pixel: Optional[float] = None,
    ax: Optional["plt.Axes"] = None,
):
    import matplotlib.pyplot as plt

    created = ax is None
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 3.8))
    else:
        fig = ax.figure

    img_disp, x_axis, y_axis, xlabel, ylabel = _display_axes(
        kymograph,
        seconds_per_line=seconds_per_line,
        um_per_pixel=um_per_pixel,
    )
    x_time, _, left_space, right_space = _result_arrays(
        results,
        seconds_per_line=seconds_per_line,
        um_per_pixel=um_per_pixel,
    )

    x_step = x_axis[1] - x_axis[0] if x_axis.size > 1 else 1.0
    y_step = y_axis[1] - y_axis[0] if y_axis.size > 1 else 1.0
    extent = [
        float(x_axis[0]),
        float(x_axis[-1] + x_step),
        float(y_axis[0]),
        float(y_axis[-1] + y_step),
    ]

    ax.imshow(img_disp, aspect="auto", origin="lower", cmap="gray", extent=extent)
    ax.plot(x_time, left_space, "c-", lw=1, label="left edge")
    ax.plot(x_time, right_space, "m-", lw=1, label="right edge")
    ax.legend(loc="upper right")

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title("Kymograph with edges")
    if created:
        fig.tight_layout()
    return fig


def plot_diameter_vs_time_mpl(
    results: list[Any],
    *,
    um_per_pixel: Optional[float] = None,
    seconds_per_line: Optional[float] = 1.0,
    use_filtered: bool = True,
    show_raw: bool = False,
    ax: Optional["plt.Axes"] = None,
):
    import matplotlib.pyplot as plt
    
    created = ax is None
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 3.2))
    else:
        fig = ax.figure

    x_time, _, left_space, right_space = _result_arrays(
        results,
        seconds_per_line=seconds_per_line,
        um_per_pixel=um_per_pixel,
    )
    diameter_raw = right_space - left_space
    diameter_filt_px = np.asarray(
        [getattr(r, "diameter_px_filt", getattr(r, "diameter_px", np.nan)) for r in results],
        dtype=float,
    )
    diameter_filt = diameter_filt_px * um_per_pixel if um_per_pixel is not None else diameter_filt_px
    diameter = diameter_filt if use_filtered else diameter_raw

    ax.plot(x_time, diameter, color="tab:blue", lw=1.5, label="diameter")
    if show_raw and use_filtered:
        ax.plot(x_time, diameter_raw, color="tab:gray", lw=1.0, alpha=0.7, label="diameter raw")
        ax.legend(loc="upper right")
    ax.set_xlabel("time (s)" if seconds_per_line is not None else "time (rows)")
    ax.set_ylabel("diameter (um)" if um_per_pixel is not None else "diameter (px)")
    ax.set_title("Diameter vs time")
    ax.grid(alpha=0.3)
    if created:
        fig.tight_layout()
    return fig


def plot_kymograph_with_edges_plotly_dict(
    kymograph: np.ndarray,
    results: list[Any],
    *,
    seconds_per_line: Optional[float] = None,
    um_per_pixel: Optional[float] = None,
) -> dict[str, Any]:
    img_disp, x_axis, y_axis, xlabel, ylabel = _display_axes(
        kymograph,
        seconds_per_line=seconds_per_line,
        um_per_pixel=um_per_pixel,
    )
    x_time, _, left_space, right_space = _result_arrays(
        results,
        seconds_per_line=seconds_per_line,
        um_per_pixel=um_per_pixel,
    )

    return {
        "data": [
            {
                "type": "heatmap",
                "z": img_disp.tolist(),
                "x": x_axis.tolist(),
                "y": y_axis.tolist(),
                "colorscale": "Gray",
                "showscale": True,
                "name": "kymograph",
            },
            {
                "type": "scatter",
                "x": x_time.tolist(),
                "y": left_space.tolist(),
                "mode": "lines",
                "name": "left edge",
                "line": {"color": "cyan"},
            },
            {
                "type": "scatter",
                "x": x_time.tolist(),
                "y": right_space.tolist(),
                "mode": "lines",
                "name": "right edge",
                "line": {"color": "magenta"},
            },
        ],
        "layout": {
            "title": "Kymograph with edges",
            "xaxis": {"title": xlabel},
            "yaxis": {"title": ylabel},
        },
    }


def plot_diameter_vs_time_plotly_dict(
    results: list[Any],
    *,
    um_per_pixel: Optional[float] = None,
    seconds_per_line: Optional[float] = 1.0,
    use_filtered: bool = True,
    show_raw: bool = False,
) -> dict[str, Any]:
    x_time, _, left_space, right_space = _result_arrays(
        results,
        seconds_per_line=seconds_per_line,
        um_per_pixel=um_per_pixel,
    )
    diameter_raw = right_space - left_space
    diameter_filt_px = np.asarray(
        [getattr(r, "diameter_px_filt", getattr(r, "diameter_px", np.nan)) for r in results],
        dtype=float,
    )
    diameter_filt = diameter_filt_px * um_per_pixel if um_per_pixel is not None else diameter_filt_px
    diameter = diameter_filt if use_filtered else diameter_raw

    data = [
        {
            "type": "scatter",
            "mode": "lines",
            "x": x_time.tolist(),
            "y": diameter.tolist(),
            "name": "diameter",
            "line": {"color": "royalblue"},
        }
    ]
    if show_raw and use_filtered:
        data.append(
            {
                "type": "scatter",
                "mode": "lines",
                "x": x_time.tolist(),
                "y": diameter_raw.tolist(),
                "name": "diameter raw",
                "line": {"color": "gray", "dash": "dash"},
            }
        )
    return {
        "data": data,
        "layout": {
            "title": "Diameter vs time",
            "xaxis": {"title": "time (s)" if seconds_per_line is not None else "time (rows)"},
            "yaxis": {
                "title": "diameter (um)" if um_per_pixel is not None else "diameter (px)"
            },
        },
    }
