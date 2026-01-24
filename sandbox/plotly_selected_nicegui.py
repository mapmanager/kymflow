# nicegui_plotly_selected_poc.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import plotly.graph_objects as go
from nicegui import ui


def _selected_xrange_from_event(e: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Compute selected x-range from a Plotly selection event payload.

    Args:
        e: NiceGUI event args dict for 'plotly_selected'.

    Returns:
        (x_min, x_max) if points exist, else None.
    """
    points: List[Dict[str, Any]] = e.get("points") or []
    if not points:
        return None

    xs: List[float] = []
    for p in points:
        x = p.get("x")
        if isinstance(x, (int, float)):
            xs.append(float(x))

    if not xs:
        return None

    return (min(xs), max(xs))


def main() -> None:
    # Synthetic data
    rng = np.random.default_rng(0)
    n = 2_000
    x = np.linspace(0.0, 10.0, n)
    y = np.sin(2 * np.pi * 0.5 * x) + 0.15 * rng.standard_normal(n)

    fig = go.Figure(go.Scattergl(x=x, y=y, mode="markers", marker=dict(size=5)))
    fig.update_layout(
        height=500,
        margin=dict(l=20, r=10, t=10, b=30),
        # This makes box-select the default interaction (instead of zoom).
        dragmode="select",
    )
    fig.update_xaxes(title="Time (s)")
    fig.update_yaxes(title="Signal")

    ui.label("Drag a box to select points (default tool: box select).").classes("text-lg")

    plot = ui.plotly(fig).classes("w-full")

    # Optional: show selection results in the UI too
    info = ui.label("Selection: (none yet)").classes("font-mono text-sm")

    def on_selected(e: Dict[str, Any]) -> None:
        xr = _selected_xrange_from_event(e)
        n_pts = len(e.get("points") or [])
        if xr is None:
            msg = f"Selection cleared (points={n_pts})"
        else:
            msg = f"Selected points={n_pts}, x-range=[{xr[0]:.4f}, {xr[1]:.4f}]"
        print(msg)
        info.text = msg

    plot.on("plotly_selected", on_selected)

    # Helpful extension: catch zoom/pan changes too
    def on_relayout(e: Dict[str, Any]) -> None:
        # For zoom/pan, Plotly emits keys like 'xaxis.range[0]' and 'xaxis.range[1]'
        if "xaxis.range[0]" in e and "xaxis.range[1]" in e:
            x0 = e["xaxis.range[0]"]
            x1 = e["xaxis.range[1]"]
            print(f"Relayout x-range = [{x0}, {x1}]")

    plot.on("plotly_relayout", on_relayout)

    ui.run(title="NiceGUI Plotly plotly_selected PoC")


if __name__ in {"__main__", "__mp_main__"}:
    main()