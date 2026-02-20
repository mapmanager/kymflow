"""NiceGUI viewer demo for dataset.zarr (AG Grid + Plotly heatmap).

Run:
    uv run python src/kymflow/core/zarr/examples/demo_nicegui_viewer_v01.py --dataset /path/to/dataset.zarr
Smoke check (no server):
    uv run python src/kymflow/core/zarr/examples/demo_nicegui_viewer_v01.py --dataset /path/to/dataset.zarr --smoke
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from kymflow.core.kym_dataset.viewer_data import build_viewer_dataframe
from kymflow_zarr import ZarrDataset


def plot_heatmap_dict(arr: np.ndarray, *, title: str = "") -> dict:
    """Build a Plotly heatmap figure dictionary.

    Args:
        arr: 2D image array.
        title: Plot title.

    Returns:
        Plotly-compatible figure dictionary.
    """
    return {
        "data": [
            {
                "type": "heatmap",
                "z": np.asarray(arr).tolist(),
                "colorscale": "Viridis",
                "showscale": True,
            }
        ],
        "layout": {"title": {"text": title}, "margin": {"l": 30, "r": 20, "t": 40, "b": 30}},
    }


def _slice_to_2d(arr: np.ndarray) -> np.ndarray:
    out = np.asarray(arr)
    while out.ndim > 2:
        out = out[0]
    if out.ndim != 2:
        raise ValueError(f"Expected 2D after slicing, got ndim={out.ndim}")
    return out


def _row_metadata(ds: ZarrDataset, image_id: str) -> dict[str, Any]:
    rec = ds.record(image_id)
    md: dict[str, Any]
    try:
        md = rec.load_metadata_payload()
    except FileNotFoundError:
        md = {}
    rois = md.get("rois", []) if isinstance(md, dict) else []
    n_rois = len(rois) if isinstance(rois, list) else 0
    header = md.get("header", {}) if isinstance(md, dict) else {}
    exp = md.get("experiment_metadata", {}) if isinstance(md, dict) else {}
    return {"n_rois": n_rois, "header": header, "experiment_metadata": exp}


def _run_ui(ds: ZarrDataset) -> None:
    from nicegui import ui

    df = build_viewer_dataframe(ds)
    if len(df) == 0:
        df = pd.DataFrame(columns=["image_id", "original_path", "acquired_local_epoch_ns"])

    print('got df:')
    print(df)


    selected = {"image_id": None}
    with ui.row().classes("w-full items-start"):
        with ui.column().classes("w-2/5 h-full min-h-0") as grid_container:
            # Required AG Grid construction pattern.
            aggrid = ui.aggrid.from_pandas(df).classes("w-full aggrid-compact")
            aggrid.options["columnDefs"] = [{"headerName": c, "field": c, "sortable": True, "resizable": True} for c in df.columns]
            aggrid.options["rowSelection"] = "single"
            aggrid.options[":getRowId"] = "(params) => params.data && String(params.data['image_id'])"
            aggrid.update()

            with ui.context_menu():
                for c in df.columns:
                    ui.menu_item(c)

        with ui.column().classes("w-3/5 h-full min-h-0"):
            plot = ui.plotly(plot_heatmap_dict(np.zeros((8, 8)), title="Select a row")).classes("w-full h-96")
            meta_label = ui.label("metadata: none")

    def on_row_selected(e: Any) -> None:
        row = e.args.get("data") if isinstance(e.args, dict) else None
        if not isinstance(row, dict):
            return
        image_id = str(row.get("image_id", ""))
        if not image_id:
            return
        selected["image_id"] = image_id
        rec = ds.record(image_id)
        arr2d = _slice_to_2d(rec.load_array())
        plot.figure = plot_heatmap_dict(arr2d, title=image_id)
        md = _row_metadata(ds, image_id)
        meta_label.text = f"n_rois={md['n_rois']} header_keys={len(md['header'])} exp_keys={len(md['experiment_metadata'])}"
        plot.update()

    aggrid.on("rowSelected", on_row_selected)
    ui.run(reload=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="NiceGUI viewer demo for dataset.zarr")
    parser.add_argument("--dataset", required=True, type=str)
    parser.add_argument("--smoke", action="store_true", default=False)
    args = parser.parse_args()

    ds = ZarrDataset(str(Path(args.dataset).resolve()), mode="a")
    if args.smoke:
        df = build_viewer_dataframe(ds)
        print("rows:", len(df))
        print("columns:", list(df.columns))
        return

    _run_ui(ds)


if __name__ == "__main__":
    main()
