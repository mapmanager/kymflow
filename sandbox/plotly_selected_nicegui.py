# sandbox/plotly_selected_nicegui.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import plotly.graph_objects as go
from nicegui import ui
from nicegui.events import GenericEventArguments


def _selected_xrange_from_points(points: List[Dict[str, Any]]) -> Optional[Tuple[float, float]]:
    """Compute selected x-range from Plotly selection event points."""
    xs: List[float] = []
    for p in points:
        x = p.get("x")
        if isinstance(x, (int, float)):
            xs.append(float(x))
    if not xs:
        return None
    return min(xs), max(xs)


async def _clear_all_roi_selections_and_selected_points(plot_div_id: str) -> None:
    """Clear both:
    1) ROI rectangles (layout.selections)
    2) The selected points that Plotly marks when a selection is made (trace.selectedpoints)
    """
    js = f"""
    (() => {{
      const gd = document.getElementById({plot_div_id!r});
      if (!gd) return;

      // (1) Clear ROI rectangles (layout.selections)
      Plotly.relayout(gd, {{ selections: [] }});

      // (2) Clear selected points styling/state
      if (gd.data && gd.data.length) {{
        const idx = Array.from({{length: gd.data.length}}, (_, i) => i);
        Plotly.restyle(gd, {{ selectedpoints: [null] }}, idx);
      }}
    }})()
    """
    await ui.run_javascript(js)


async def _set_dragmode(plot_div_id: str, dragmode: Optional[str]) -> None:
    """Set Plotly dragmode.

    dragmode options:
      - "select" : box select (ROI drawing)
      - "lasso"  : lasso select
      - "zoom"   : normal zoom
      - False    : disable drag interactions
    """
    js = f"""
    (() => {{
      const gd = document.getElementById({plot_div_id!r});
      if (!gd) return;
      Plotly.relayout(gd, {{ dragmode: {repr(dragmode)} }});
    }})()
    """
    await ui.run_javascript(js)


def main() -> None:
    rng = np.random.default_rng(0)
    n = 2_000
    x = np.linspace(0.0, 10.0, n)
    y = np.sin(2 * np.pi * 0.5 * x) + 0.15 * rng.standard_normal(n)

    fig = go.Figure(go.Scattergl(x=x, y=y, mode="markers", marker=dict(size=5)))
    fig.update_layout(
        height=500,
        margin=dict(l=20, r=10, t=10, b=30),
        dragmode="select",  # default drag is box select (ROI draw ON)
    )
    fig.update_xaxes(title="Time (s)")
    fig.update_yaxes(title="Signal")

    ui.label("Drag a box to select points (ROI draw ON by default).").classes("text-lg")

    # abb: give the plot a stable DOM id so JS can find it
    PLOT_DIV_ID = "plotly_kym_movie"

    plot = ui.plotly(fig).classes("w-full")
    plot.props(f"id={PLOT_DIV_ID}")

    info = ui.label("Selection: (none yet)").classes("font-mono text-sm")

    # ------------------------------------------------------------
    # ROI + dragmode controls
    # ------------------------------------------------------------

    with ui.row().classes("gap-2"):
        # abb: enable ROI drawing (box select)
        async def on_enable_roi() -> None:
            await _set_dragmode(PLOT_DIV_ID, "select")
            info.text = "Dragmode: select (ROI draw enabled)"

        ui.button("Enable ROI draw", on_click=on_enable_roi)

        # abb: disable ROI drawing, return to normal zoom behavior
        async def on_disable_roi() -> None:
            await _set_dragmode(PLOT_DIV_ID, "zoom")
            info.text = "Dragmode: zoom (ROI draw disabled)"

        ui.button("Disable ROI draw", on_click=on_disable_roi)

        # abb: clear ROI(s) means clear layout.selections AND selected points
        async def on_clear_rois() -> None:
            await _clear_all_roi_selections_and_selected_points(PLOT_DIV_ID)
            info.text = "Selection: (cleared ROI selections + selected points)"

        ui.button("Clear ROI(s)", on_click=on_clear_rois)

    # ------------------------------------------------------------
    # Plotly relayout handler (ROI tracking)
    # ------------------------------------------------------------

    def on_relayout(e: GenericEventArguments) -> None:
        """
        Handle Plotly relayout events.
        This is the only way to get the selection x-range when the user is dragging a box.
        """
        payload: Dict[str, Any] = e.args

        print('=== in on_relayout() payload is:')
        from pprint import pprint
        pprint(payload)

        x0, x1 = None, None
        if 'selections[0].x0' in payload.keys():
            print('  update "selections[0].x0" found')
            x0 = payload['selections[0].x0']
            x1 = payload['selections[0].x1']
            print(f"  -> update Selection: x-range = [{x0}, {x1}]")
        elif 'selections' not in payload.keys():
            return

        # on new selection
        if x0 is None and x1 is None:
            selections = payload['selections']
            if selections:
                for _idx, selection in enumerate(selections):
                    _type = selection['type']
                    if _type != 'rect':
                        continue
                    x0 = selection['x0']
                    x1 = selection['x1']
                    print(f"  -> new Selection: {_type} x-range = [{x0}, {x1}] (idx={_idx})")

    plot.on("plotly_relayout", on_relayout)

    ui.run(title="NiceGUI Plotly ROI + dragmode toggle PoC")


if __name__ in {"__main__", "__mp_main__"}:
    main()