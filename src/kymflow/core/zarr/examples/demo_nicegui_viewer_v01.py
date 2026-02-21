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

from nicegui import ui

from kymflow.core.kym_dataset.viewer_data import build_viewer_dataframe
from kymflow_zarr import ZarrDataset

_ds: ZarrDataset | None = None

def plot_heatmap_dict(arr: np.ndarray, *,  transpose:bool = False, title: str = "") -> dict:
    """Build a Plotly heatmap figure dictionary.

    Args:
        arr: 2D image array.
        title: Plot title.

    Returns:
        Plotly-compatible figure dictionary.
    """
    if transpose:
        arr = arr.transpose()
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
    
    from pprint import pprint
    print('got md:')
    pprint(md, sort_dicts=False, indent=4)
    
    rois = md.get("rois", []) if isinstance(md, dict) else []
    n_rois = len(rois) if isinstance(rois, list) else 0
    header = md.get("header", {}) if isinstance(md, dict) else {}
    exp = md.get("experiment_metadata", {}) if isinstance(md, dict) else {}
    return {"n_rois": n_rois, "header": header, "experiment_metadata": exp}


# def _run_ui(ds: ZarrDataset) -> None:

@ui.page("/")
def home() -> None:

    global _ds
    if _ds is None:
        raise ValueError("Dataset not initialized")

    df = build_viewer_dataframe(_ds)
    if len(df) == 0:
        df = pd.DataFrame(columns=["image_id", "original_path", "acquired_local_epoch_ns"])

    print('got df:')
    print(df)


    selected = {"image_id": None}
    with ui.row().classes("w-full items-start"):
        with ui.column().classes("w-full h-full min-h-0") as grid_container:
            # Required AG Grid construction pattern.
            aggrid = ui.aggrid.from_pandas(df).classes("w-full aggrid-compact")
            aggrid.options["columnDefs"] = [{"headerName": c, "field": c, "sortable": True, "resizable": True} for c in df.columns]
            aggrid.options["rowSelection"] = "single"
            aggrid.options[":getRowId"] = "(params) => params.data && String(params.data['image_id'])"
            aggrid.update()

            # with ui.context_menu():
            #     for c in df.columns:
            #         ui.menu_item(c)

        with ui.column().classes("w-full h-full min-h-0"):
            plot = ui.plotly(plot_heatmap_dict(np.zeros((8, 8)), transpose=True, title="Select a row")).classes("w-full h-96")
            meta_label = ui.label("metadata: none")

    def on_row_selected(e: Any) -> None:
        row = e.args.get("data") if isinstance(e.args, dict) else None
        if not isinstance(row, dict):
            return
        image_id = str(row.get("image_id", ""))
        if not image_id:
            return
        selected["image_id"] = image_id
        rec = _ds.record(image_id)
        _arr = rec.load_array()
        print(f'got arr: {_arr.shape}')
        arr2d = _slice_to_2d(_arr)
        plot.figure = plot_heatmap_dict(arr2d, transpose=True, title=image_id)
        md = _row_metadata(_ds, image_id)
        meta_label.text = f"n_rois={md['n_rois']} header_keys={len(md['header'])} exp_keys={len(md['experiment_metadata'])}"
        plot.update()

    aggrid.on("rowSelected", on_row_selected)



def main() -> None:
    parser = argparse.ArgumentParser(description="NiceGUI viewer demo for dataset.zarr")
    parser.add_argument("--dataset", required=True, type=str)
    parser.add_argument("--smoke", action="store_true", default=False)
    args = parser.parse_args()

    _path = args.dataset
    # _path = "src/kymflow/core/zarr/examples/demo_nicegui_viewer_v01.py --dataset /Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/zarr-data/tmp-dataset"

    ds = ZarrDataset(str(Path(_path).resolve()), mode="a")
    global _ds
    _ds = ds

    if args.smoke:
        df = build_viewer_dataframe(ds)
        print("rows:", len(df))
        print("columns:", list(df.columns))
        return

    # _run_ui(ds)
    _native = True
    ui.run(reload=False, native=_native)


if __name__ in {"__main__", "__mp_main__"}:
    main()
