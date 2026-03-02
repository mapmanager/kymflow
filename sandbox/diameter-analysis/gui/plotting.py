from __future__ import annotations

from typing import Any, Optional

import numpy as np


def _time_axis(n_time: int, seconds_per_line: float) -> np.ndarray:
    return np.arange(n_time, dtype=float) * float(seconds_per_line)


def _space_axis(n_space: int, um_per_pixel: float) -> np.ndarray:
    return np.arange(n_space, dtype=float) * float(um_per_pixel)


def make_kymograph_figure_dict(
    img: np.ndarray,
    *,
    seconds_per_line: float,
    um_per_pixel: float,
    title: str = "Kymograph",
) -> dict:
    if img.ndim != 2:
        raise ValueError("img must be 2D (time, space)")
    n_time, n_space = img.shape
    x = _time_axis(n_time, seconds_per_line)
    y = _space_axis(n_space, um_per_pixel)

    z = img.transpose()  # (space, time) so x=time, y=space

    return {
        "data": [
            {
                "type": "heatmap",
                "x": x.tolist(),
                "y": y.tolist(),
                "z": z.tolist(),
                "colorbar": {"title": "intensity"},
            }
        ],
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": "time (s)"},
            "yaxis": {"title": "space (um)"},
            "margin": {"l": 55, "r": 20, "t": 40, "b": 45},
        },
    }


def overlay_edges_on_kymograph_dict(
    fig: dict,
    *,
    seconds: np.ndarray,
    left_um: Optional[np.ndarray] = None,
    right_um: Optional[np.ndarray] = None,
    center_um: Optional[np.ndarray] = None,
) -> dict:
    data = list(fig.get("data", []))

    def _add_trace(name: str, y: np.ndarray):
        data.append({
            "type": "scatter",
            "mode": "lines",
            "name": name,
            "x": seconds.tolist(),
            "y": y.tolist(),
            "line": {"width": 2},
        })

    if left_um is not None:
        _add_trace("left", left_um)
    if right_um is not None:
        _add_trace("right", right_um)
    if center_um is not None:
        _add_trace("center", center_um)

    fig2 = dict(fig)
    fig2["data"] = data
    return fig2


def set_xrange(fig: dict, x0: float, x1: float) -> dict:
    fig2 = dict(fig)
    layout = dict(fig2.get("layout", {}))
    xaxis = dict(layout.get("xaxis", {}))
    xaxis["range"] = [float(x0), float(x1)]
    layout["xaxis"] = xaxis
    fig2["layout"] = layout
    return fig2


def _extract_diameter_um(results: Any, um_per_pixel: float) -> Optional[np.ndarray]:
    # pandas DataFrame
    try:
        import pandas as pd  # type: ignore
        if isinstance(results, pd.DataFrame):
            df = results
            if "diameter_um" in df.columns:
                return df["diameter_um"].to_numpy(dtype=float, copy=False)
            if "diameter_px" in df.columns:
                return (df["diameter_px"].to_numpy(dtype=float, copy=False) * float(um_per_pixel))
            # compute from edges if available
            if "left_edge_um" in df.columns and "right_edge_um" in df.columns:
                return (df["right_edge_um"].to_numpy(dtype=float, copy=False) -
                        df["left_edge_um"].to_numpy(dtype=float, copy=False))
            if "left_edge_px" in df.columns and "right_edge_px" in df.columns:
                return ((df["right_edge_px"].to_numpy(dtype=float, copy=False) -
                         df["left_edge_px"].to_numpy(dtype=float, copy=False)) * float(um_per_pixel))
            return None
    except Exception:
        pass

    # list of dataclasses/objects
    if isinstance(results, list) and results:
        # try diameter_um / diameter_px else right-left
        vals = []
        for r in results:
            if hasattr(r, "diameter_um"):
                v = getattr(r, "diameter_um")
                vals.append(np.nan if v is None else float(v))
            elif hasattr(r, "diameter_px"):
                v = getattr(r, "diameter_px")
                vals.append(np.nan if v is None else float(v) * float(um_per_pixel))
            elif hasattr(r, "left_edge_px") and hasattr(r, "right_edge_px"):
                l = getattr(r, "left_edge_px")
                rr = getattr(r, "right_edge_px")
                if l is None or rr is None:
                    vals.append(np.nan)
                else:
                    vals.append((float(rr) - float(l)) * float(um_per_pixel))
            else:
                return None
        return np.asarray(vals, dtype=float)

    return None


def _nanmedian(a: np.ndarray) -> float:
    a2 = a[~np.isnan(a)]
    if a2.size == 0:
        return float("nan")
    return float(np.median(a2))


def _nanmad(a: np.ndarray) -> float:
    a2 = a[~np.isnan(a)]
    if a2.size == 0:
        return float("nan")
    med = np.median(a2)
    return float(np.median(np.abs(a2 - med)))


def apply_post_filter_1d(values: np.ndarray, params: Any) -> np.ndarray:
    # expects params has: enabled, filter_type, kernel_size, hampel_n_sigma
    enabled = bool(getattr(params, "enabled", False))
    if not enabled:
        return values.copy()

    ftype = getattr(params, "filter_type", None)
    # filter_type may be Enum or string
    if hasattr(ftype, "value"):
        ftype = ftype.value
    ftype = str(ftype) if ftype is not None else "median"

    k = int(getattr(params, "kernel_size", 3))
    if k < 1:
        return values.copy()
    if k % 2 == 0:
        k += 1
    half = k // 2

    x = values.astype(float, copy=True)

    if ftype == "median":
        out = x.copy()
        for i in range(x.size):
            lo = max(0, i - half)
            hi = min(x.size, i + half + 1)
            out[i] = _nanmedian(x[lo:hi])
            if np.isnan(x[i]):
                out[i] = np.nan
        return out

    if ftype == "hampel":
        n_sigma = float(getattr(params, "hampel_n_sigma", 3.0))
        out = x.copy()
        for i in range(x.size):
            if np.isnan(x[i]):
                continue
            lo = max(0, i - half)
            hi = min(x.size, i + half + 1)
            win = x[lo:hi]
            med = _nanmedian(win)
            mad = _nanmad(win)
            if np.isnan(med) or np.isnan(mad) or mad == 0.0:
                continue
            sigma = 1.4826 * mad
            if abs(x[i] - med) > n_sigma * sigma:
                out[i] = med
        return out

    # unknown type -> no-op
    return x.copy()


def make_diameter_figure_dict(
    results: Any,
    *,
    seconds_per_line: float,
    um_per_pixel: float,
    post_filter_params: Any = None,
    title: str = "Diameter vs time",
) -> dict:
    if results is None:
        return {
            "data": [],
            "layout": {
                "title": {"text": title},
                "xaxis": {"title": "time (s)"},
                "yaxis": {"title": "diameter (um)"},
                "margin": {"l": 55, "r": 20, "t": 40, "b": 45},
            },
        }

    d_um = _extract_diameter_um(results, um_per_pixel=float(um_per_pixel))
    if d_um is None:
        return {
            "data": [],
            "layout": {
                "title": {"text": f"{title} (no diameter field found)"},
                "xaxis": {"title": "time (s)"},
                "yaxis": {"title": "diameter (um)"},
                "margin": {"l": 55, "r": 20, "t": 40, "b": 45},
            },
        }

    t = _time_axis(len(d_um), seconds_per_line=float(seconds_per_line))

    traces = [{
        "type": "scatter",
        "mode": "lines",
        "name": "raw",
        "x": t.tolist(),
        "y": d_um.tolist(),
        "line": {"width": 2},
    }]

    if post_filter_params is not None and bool(getattr(post_filter_params, "enabled", False)):
        d_f = apply_post_filter_1d(d_um, post_filter_params)
        traces.append({
            "type": "scatter",
            "mode": "lines",
            "name": "filtered",
            "x": t.tolist(),
            "y": d_f.tolist(),
            "line": {"width": 2, "dash": "dot"},
        })

    return {
        "data": traces,
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": "time (s)"},
            "yaxis": {"title": "diameter (um)"},
            "margin": {"l": 55, "r": 20, "t": 40, "b": 45},
            "legend": {"orientation": "h"},
        },
    }
