#!/usr/bin/env python3
"""
NiceGUI + AG Grid:

- Toggle between:
    - City column using agSelectCellEditor (dropdown only)
    - City column using default text editor (plain editable cell)
- Other NiceGUI/AG Grid niceties:
    - Zebra rows, hover highlight, tighter layout
    - Prints edits to console
"""
from typing import Any

from nicegui import ui, events
import pandas as pd

# ---------------------------------------------------------------------------
# Toggle: set this to True to use agSelectCellEditor for "City" column.
# Set to False to revert "City" to a normal editable text cell.
# ---------------------------------------------------------------------------
USE_CITY_SELECT_EDITOR = False


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

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
unique_cities = sorted(df["city"].unique().tolist())


# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------

def on_cell_value_changed(e: events.GenericEventArguments) -> None:
    """Handle AG Grid `cellValueChanged` events from NiceGUI."""
    args: dict[str, Any] = e.args
    # print('DEBUG args:', args)  # uncomment if you want to inspect again

    row_index = args.get("rowIndex")     # e.g. 0
    field = args.get("colId")           # e.g. 'city'
    old_value = args.get("oldValue")
    new_value = args.get("newValue")
    row_data = args.get("data") or {}   # full row as dict

    if row_index is None or field is None:
        print("cellValueChanged event missing rowIndex or colId:", args)
        return

    # If df has the default RangeIndex [0, 1, 2, ...], this is fine:
    df.at[row_index, field] = new_value

    # If you ever change df's index, a slightly safer variant is:
    # df.at[df.index[row_index], field] = new_value

    print(
        f"[EDIT] row={row_index}, field='{field}', "
        f"old={old_value!r}, new={new_value!r}"
    )
    print("Updated row (from df):", df.loc[row_index].to_dict())
    # Or directly from the event, if you like:
    # print("Updated row (from event):", row_data)

# ---------------------------------------------------------------------------
# Global CSS for styling
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

with ui.header().classes("py-2 px-4"):
    ui.label("NiceGUI AG Grid — City Select Editor Toggle")

ui.label(
    f"USE_CITY_SELECT_EDITOR = {USE_CITY_SELECT_EDITOR} "
    "(City column is dropdown if True, plain text if False)."
).classes("mb-2")

# Build column definitions, with City column behavior depending on the flag
city_column_def: dict

if USE_CITY_SELECT_EDITOR:
    # Use AG Grid's built-in select editor (dropdown only, no free text)
    city_column_def = {
        "headerName": "City",
        "field": "city",
        "editable": True,
        # Colon prefix: NiceGUI treats value as JS expression, not string.
        # This becomes cellEditor: 'agSelectCellEditor' in AG Grid.
        ":cellEditor": "'agSelectCellEditor'",
        "cellEditorParams": {
            "values": unique_cities,
        },
    }
else:
    # Plain text editor: just mark it editable, no special editor
    city_column_def = {
        "headerName": "City",
        "field": "city",
        "editable": True,
    }

column_defs = [
    {"headerName": "ID", "field": "id", "editable": False},
    # Make Name editable with default editor so you can compare behavior
    {"headerName": "Name", "field": "name", "editable": True},
    {"headerName": "Age", "field": "age", "editable": False},
    city_column_def,
    {"headerName": "Score", "field": "score", "editable": False},
]

_filter = False

with ui.column().classes("w-full h-80 ag-theme-alpine"):
    grid = ui.aggrid(
        {
            "columnDefs": column_defs,
            "rowData": row_data,
            "defaultColDef": {
                "sortable": True,
                "filter": _filter,
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
