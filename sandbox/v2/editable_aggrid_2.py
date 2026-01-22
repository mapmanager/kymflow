#!/usr/bin/env python3
"""
Two NiceGUI AG Grids:

1) First grid:
   - editable subset of columns
   - zebra rows, hover highlight, tight layout
   - prints cell edits to console

2) Second grid:
   - single-click row selection (no checkboxes UI)
   - selected row highlighted bright yellow
   - prints entire selected row to console
"""

from nicegui import ui
import pandas as pd


def make_dataframe() -> pd.DataFrame:
    """Create a simple demo DataFrame."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "name": ["Alice", "Bob", "Carol", "Dave"],
            "age": [25, 31, 40, 22],
            "city": ["Sacramento", "Baltimore", "Montreal", "Davis"],
            "score": [88.5, 92.0, 76.5, 89.0],
        }
    )


df = make_dataframe()
row_data = df.to_dict(orient="records")

# Column defs shared between grids
column_defs = [
    {"headerName": "ID", "field": "id", "editable": False},
    {"headerName": "Name", "field": "name", "editable": True},
    {"headerName": "Age", "field": "age", "editable": True},
    {"headerName": "City", "field": "city", "editable": True},
    {"headerName": "Score", "field": "score", "editable": False},
]


# ------------------------------------------------------------------------------
# First grid: editable cells
# ------------------------------------------------------------------------------

def on_cell_value_changed(e) -> None:
    """Handle AG Grid `cellValueChanged` events for the first grid."""
    row_index = e.args.get("rowIndex")
    col_def = e.args.get("colDef") or {}
    field = col_def.get("field")
    old_value = e.args.get("oldValue")
    new_value = e.args.get("newValue")

    if row_index is None or field is None:
        print("Bad cellValueChanged event:", e.args)
        return

    df.at[row_index, field] = new_value

    print(
        f"[EDIT] row={row_index}, field='{field}', old={old_value!r}, new={new_value!r}"
    )
    print("Updated row:", df.loc[row_index].to_dict())


# ------------------------------------------------------------------------------
# Global CSS (zebra striping, tighter layout, row selection highlight)
# ------------------------------------------------------------------------------

ui.add_head_html(
    """
<style>
/* Zebra rows for all AG Grids */
.ag-theme-alpine .ag-row-even .ag-cell {
    background-color: #f7f7f7;
}
.ag-theme-alpine .ag-row-odd .ag-cell {
    background-color: #ffffff;
}

/* Hover for all AG Grids */
.ag-theme-alpine .ag-row-hover .ag-cell {
    background-color: #e8f3ff;
}

/* Tighter layout for all AG Grids */
.ag-theme-alpine .ag-cell,
.ag-theme-alpine .ag-header-cell {
    padding: 2px 6px;
    font-size: 0.80rem;
    line-height: 1.2;
}

/* Bright yellow highlight for selected rows (used by second grid) */
.ag-theme-alpine .ag-row-selected .ag-cell {
    background-color: #fffaa0 !important;
}
</style>
"""
)


# ------------------------------------------------------------------------------
# UI Layout
# ------------------------------------------------------------------------------

with ui.header().classes("py-2 px-4"):
    ui.label("NiceGUI AG Grid Examples")


# ─────────────────────────────────────────────────────────────────────────────
#  FIRST TABLE (editable, same as before)
# ─────────────────────────────────────────────────────────────────────────────

ui.label("Editable Table").classes("text-lg mt-3")

with ui.column().classes("w-full h-72 ag-theme-alpine"):
    grid1 = ui.aggrid(
        {
            "columnDefs": column_defs,
            "rowData": row_data,
            "defaultColDef": {
                "sortable": True,
                "filter": True,
                "resizable": True,
            },
            "rowSelection": "single",
            "stopEditingWhenCellsLoseFocus": True,
            "rowHeight": 28,
            "headerHeight": 30,
        }
    )

    grid1.on("cellValueChanged", on_cell_value_changed)


# ─────────────────────────────────────────────────────────────────────────────
#  SECOND TABLE (row selection on click, yellow highlight, print row)
# ─────────────────────────────────────────────────────────────────────────────

ui.label("Row Selection Table (click a row)").classes("text-lg mt-6")

with ui.column().classes("w-full h-72 ag-theme-alpine"):
    grid2 = ui.aggrid(
        {
            "columnDefs": column_defs,
            "rowData": row_data,
            "defaultColDef": {
                "sortable": True,
                "filter": True,
                "resizable": True,
            },
            # This enables selection on row click (no extra options needed)
            "rowSelection": "single",
            "rowHeight": 28,
            "headerHeight": 30,
        }
    )

    # When a row is selected, AG Grid fires `rowSelected`:
    #   e.args has keys like: rowIndex, data, selected, etc.
    def on_row_selected(e):
        args = e.args or {}
        if not args.get("selected"):
            # ignore deselection events, only log when a row becomes selected
            return
        row = args.get("data")
        print("[ROW SELECTED]", row)

    grid2.on("rowSelected", on_row_selected)


# ------------------------------------------------------------------------------
# Run
# ------------------------------------------------------------------------------

if __name__ in {"__main__", "__mp_main__"}:
    ui.run()
