# demo_ui_select_controller_aggrid_gold_standard.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd
from nicegui import ui
from nicegui.events import GenericEventArguments


def gold_standard_aggrid(
    df: pd.DataFrame,
    *,
    unique_row_id_col: str | None = None,
    row_select_callback: Callable[[Any | None, dict[str, Any]], None] | None = None,
    keep: list[str] | None = None,
) -> ui.aggrid:
    """Known-good NiceGUI 3.7.1 AG Grid construction pattern (from_pandas, set options after)."""

    def _on_row_selected(e: GenericEventArguments) -> None:
        row_dict = e.args.get("data")
        if not isinstance(row_dict, dict):
            return

        unique_id = None
        if unique_row_id_col is not None and unique_row_id_col in row_dict:
            unique_id = row_dict[unique_row_id_col]

        if row_select_callback is not None:
            row_select_callback(unique_id, row_dict)

    with ui.column().classes("w-full h-full min-h-0"):
        aggrid = ui.aggrid.from_pandas(df).classes("w-full aggrid-compact")

        cols = list(df.columns)
        keep_set = set(keep) if keep else None

        aggrid.options["columnDefs"] = [
            {
                "headerName": c,
                "field": c,
                "hide": (keep_set is not None and c not in keep_set),
                "checkboxSelection": False,
                "headerCheckboxSelection": False,
                "sortable": True,
                "resizable": True,
            }
            for c in cols
        ]

        aggrid.options["rowSelection"] = "single"
        aggrid.options["suppressRowClickSelection"] = False

        aggrid.update()

    if row_select_callback is not None:
        aggrid.on("rowSelected", _on_row_selected)

    return aggrid


@dataclass
class MetadataChangeEvent:
    """A simple event object representing a proposed metadata change."""
    row_id: int
    field: str
    value: str


class Controller:
    """Mock controller:
    - receives proposed changes
    - mutates the DataFrame
    - emits a 'changed' callback
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df
        self._on_changed: Callable[[MetadataChangeEvent], None] | None = None

    def on_changed(self, cb: Callable[[MetadataChangeEvent], None]) -> None:
        self._on_changed = cb

    def apply_change(self, ev: MetadataChangeEvent) -> None:
        # mutate df
        mask = self.df["id"] == ev.row_id
        if not mask.any():
            print(f"[controller] row_id not found: {ev.row_id}")
            return

        self.df.loc[mask, ev.field] = ev.value
        print(f"[controller] mutated df: id={ev.row_id} {ev.field}={ev.value}")

        # emit changed
        if self._on_changed:
            self._on_changed(ev)


@ui.page("/")
def home() -> None:
    ui.page_title("Gold-standard AG Grid + ui.select demo (NiceGUI 3.7.1)")

    # ---- mock data ----
    df = pd.DataFrame([
        {"id": 1, "condition": "control", "treatment": "vehicle", "genotype": "wt", "vel_mean": 1.1, "file_name": "A.tif"},
        {"id": 2, "condition": "control", "treatment": "drug",    "genotype": "wt", "vel_mean": 1.2, "file_name": "B.tif"},
        {"id": 3, "condition": "stim",    "treatment": "drug",    "genotype": "ko", "vel_mean": 2.0, "file_name": "C.tif"},
    ])

    controller = Controller(df)

    # current selected row_id
    selected = {"row_id": int(df.iloc[0]["id"])}

    def set_selected_row(row_id: Any | None, row_dict: dict[str, Any]) -> None:
        if row_id is None:
            return
        selected["row_id"] = int(row_id)
        print(f"[view] selected row_id={selected['row_id']}")
        # update selects to reflect selected row
        row = df.loc[df["id"] == selected["row_id"]].iloc[0]
        sel_condition.value = str(row["condition"])
        sel_treatment.value = str(row["treatment"])
        sel_genotype.value = str(row["genotype"])

    def refresh_grid_full() -> None:
        """Simple + reliable: replace rowData and update grid."""
        # This is the most reliable way when you're fighting rendering issues.
        # Later you can optimize to applyTransaction once baseline works.
        row_data = df.to_dict("records")
        grid.options["rowData"] = row_data
        grid.update()
        print("[grid] full refresh rowData")

    def on_controller_changed(ev: MetadataChangeEvent) -> None:
        # push df change back to grid
        refresh_grid_full()

    controller.on_changed(on_controller_changed)

    with ui.column().classes("w-full h-full min-h-0 gap-3"):
        ui.label("Gold-standard AG Grid pattern + Controller-driven edits").classes("text-lg font-semibold")

        # ---- selects (preset options + allow new entries) ----
        def unique_options(col: str) -> list[str]:
            return sorted({str(x) for x in df[col].dropna().unique().tolist()})

        # NOTE: NiceGUI select allows arbitrary values with `new_value_mode="add"`
        # (this is the behavior you wanted: preset options + allow typing new)
        with ui.row().classes("w-full gap-2 items-end"):
            sel_condition = ui.select(
                options=unique_options("condition"),
                label="condition",
                value=str(df.iloc[0]["condition"]),
                new_value_mode="add",
            ).classes("w-64")

            sel_treatment = ui.select(
                options=unique_options("treatment"),
                label="treatment",
                value=str(df.iloc[0]["treatment"]),
                new_value_mode="add",
            ).classes("w-64")

            sel_genotype = ui.select(
                options=unique_options("genotype"),
                label="genotype",
                value=str(df.iloc[0]["genotype"]),
                new_value_mode="add",
            ).classes("w-64")

        def emit_change(field: str, value: str) -> None:
            row_id = selected["row_id"]
            controller.apply_change(MetadataChangeEvent(row_id=row_id, field=field, value=value))

        sel_condition.on_value_change(lambda e: emit_change("condition", str(e.value)))
        sel_treatment.on_value_change(lambda e: emit_change("treatment", str(e.value)))
        sel_genotype.on_value_change(lambda e: emit_change("genotype", str(e.value)))

        # ---- grid (gold-standard build) ----
        grid = gold_standard_aggrid(
            df,
            unique_row_id_col="id",
            row_select_callback=set_selected_row,
            keep=["id", "vel_mean", "file_name", "condition", "treatment", "genotype"],
        )

        # IMPORTANT: ensure rowData is definitely present (from_pandas usually sets it)
        # but we can be explicit to avoid any weirdness:
        grid.options["rowData"] = df.to_dict("records")
        grid.update()
        print("[grid] initial rowData set + update")

        with ui.row().classes("gap-2"):
            ui.button("Full refresh grid (debug)", on_click=refresh_grid_full)
            ui.button("Print selected row_id", on_click=lambda: print(f"[debug] selected={selected['row_id']}"))

    # Use an open port if you want:
    # ui.run(reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    # home()
    ui.run(reload=False, native=True)