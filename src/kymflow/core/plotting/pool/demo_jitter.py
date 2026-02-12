# app_swarm.py
from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd
from nicegui import ui


def make_swarm_plotly_dict(
    df: pd.DataFrame,
    *,
    x_cat_col: str,
    y_col: str,
    title: str = "Swarm (strip) plot",
    jitter: float = 0.35,
) -> Dict[str, Any]:
    """
    Plotly "swarm-ish" plot:
      - x is categorical (one bin per unique value)
      - y is continuous
      - points are jittered horizontally within each category
    Uses Plotly's built-in jitter/pointpos (strip-plot style) and returns a plotly dict.
    """
    x = df[x_cat_col].astype(str).tolist()
    y = pd.to_numeric(df[y_col], errors="coerce").tolist()

    plotly_dict: Dict[str, Any] = {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "x": x,
                "y": y,
                # "swarm-ish" horizontal spreading within each category bin
                "jitter": jitter,
                "pointpos": 0.0,
                # optional hover
                "hovertemplate": (
                    f"{x_cat_col}=%{{x}}<br>"
                    f"{y_col}=%{{y}}<extra></extra>"
                ),
                "name": y_col,
            }
        ],
        "layout": {
            "title": {"text": title},
            "margin": {"l": 50, "r": 20, "t": 50, "b": 80},
            "xaxis": {
                "title": {"text": x_cat_col},
                "type": "category",
                "tickangle": -30,
            },
            "yaxis": {"title": {"text": y_col}},
            # keep zoom/pan stable across updates if you later replot
            "uirevision": "keep",
        },
    }
    return plotly_dict


def main() -> None:
    # Demo df (replace with your real df)
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "condition": (["ctrl"] * 40) + (["drug"] * 40) + (["wash"] * 40),
            "value": np.concatenate(
                [
                    rng.normal(0.0, 0.8, 40),
                    rng.normal(1.0, 0.8, 40),
                    rng.normal(0.4, 0.8, 40),
                ]
            ),
        }
    )

    ui.page_title("NiceGUI Plotly swarm")
    ui.label("Plotly dict-based swarm/strip plot").classes("text-lg font-medium")

    plot = ui.plotly(
        make_swarm_plotly_dict(df, x_cat_col="condition", y_col="value")
    ).classes("w-full")

    # tiny UI to show it's re-plottable
    def randomize() -> None:
        df2 = df.copy()
        df2["value"] = df2["value"] + rng.normal(0, 0.3, len(df2))
        plot.figure = make_swarm_plotly_dict(df2, x_cat_col="condition", y_col="value", title="Swarm (updated)")

    ui.button("Randomize Y a bit", on_click=randomize)

    ui.run(reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()