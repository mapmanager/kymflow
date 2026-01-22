#!/usr/bin/env python3
"""
NiceGUI + AG Grid editable example with styling:

- zebra (alternating) row colors
- tighter layout (smaller font, less padding)
- editable subset of columns
- prints edits to console
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

# Only some columns are editable
column_defs = [
    {"headerName": "ID", "field": "id", "editable": False},
    {"headerName": "Name", "field": "name", "editable": True},
    {"headerName": "Age", "field": "age", "editable": True},
    {"headerName": "City", "field": "city", "editable": True},
    {"headerName": "Score", "field": "score", "editable": False},
]


def on_cell_value_changed(e) -> None:
    """Handle AG Grid `cellValueChanged` events."""
    row_index = e.args.get("rowIndex")
    col_def = e.args.get("colDef") or {}
    field = col_def.get("field")
    old_value = e.args.get("oldValue")
    new_value = e.args.get("newValue")

    if row_index is None or field is None:
        print("cellValueChanged event missing rowIndex or field:", e.args)
        return

    # Update the pandas DataFrame
    df.at[row_index, field] = new_value

    # Print to console
    print(
        f"Cell edited: row={row_index}, column='{field}', "
        f"old={old_value!r}, new={new_value!r}"
    )
    print("Updated row:", df.loc[row_index].to_dict())


# ---- Global CSS for zebra rows + tight layout -------------------------------

ui.add_head_html(
    """
<style>
/* Zebra rows: even / odd backgrounds */
.ag-theme-alpine .ag-row-even .ag-cell {
    background-color: #f7f7f7;
}
.ag-theme-alpine .ag-row-odd .ag-cell {
    background-color: #ffffff;
}

/* Slightly different hover color */
.ag-theme-alpine .ag-row-hover .ag-cell {
    background-color: #e8f3ff;
}

/* Tighter layout: smaller font + less padding */
.ag-theme-alpine .ag-cell,
.ag-theme-alpine .ag-header-cell {
    padding: 2px 6px;
    font-size: 0.80rem;
    line-height: 1.2;
}
</style>
"""
)


# ---- UI --------------------------------------------------------------------

with ui.header().classes("py-2 px-4"):
    ui.label("NiceGUI AG Grid — Styled & Editable DataFrame")

ui.label(
    "Only 'name', 'age', and 'city' are editable. "
    "Changes are printed to the console."
).classes("mb-2")

with ui.column().classes("w-full h-96 ag-theme-alpine"):
    grid = ui.aggrid(
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

    grid.on("cellValueChanged", on_cell_value_changed)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run()
