#!/usr/bin/env python3
"""
NiceGUI + AG Grid with custom combo-box-like editor for one column.

Behavior:
- Show a table backed by a pandas DataFrame.
- Only the "city" column uses a custom editor:
    - On edit, user sees a dropdown of unique city values.
    - Editor is an <input list="..."> with a <datalist> of unique values.
    - User can still type any new value that isn't in the list.
- Edits are written back into the DataFrame and printed to the console.
"""

from nicegui import ui
import pandas as pd


# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

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

# Unique values for the combo editor (can be passed as editor params)
unique_cities = sorted(df["city"].unique().tolist())


# -----------------------------------------------------------------------------
# Event handlers
# -----------------------------------------------------------------------------

def on_cell_value_changed(e) -> None:
    """
    Handle AG Grid `cellValueChanged` events.

    We update the global DataFrame and print the changed row.
    """
    row_index = e.args.get("rowIndex")
    col_def = e.args.get("colDef") or {}
    field = col_def.get("field")
    old_value = e.args.get("oldValue")
    new_value = e.args.get("newValue")

    if row_index is None or field is None:
        print("cellValueChanged event missing rowIndex or field:", e.args)
        return

    df.at[row_index, field] = new_value

    print(
        f"[EDIT] row={row_index}, field='{field}', "
        f"old={old_value!r}, new={new_value!r}"
    )
    print("Updated row:", df.loc[row_index].to_dict())


# -----------------------------------------------------------------------------
# Global CSS and JS (zebra rows, tight layout, custom editor)
# -----------------------------------------------------------------------------

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

<script>
// A custom AG Grid cell editor that behaves like a combo box:
// - Uses <input list="..."> with a <datalist> of suggested values.
// - Suggests values from params.cellEditorParams.values (if provided).
// - Still allows the user to type any arbitrary text.
function CityComboEditor() {}

CityComboEditor.prototype.init = function(params) {
    this.params = params;

    // Container for the editor
    this.container = document.createElement('span');

    // Text input with datalist suggestions
    const input = document.createElement('input');
    input.type = 'text';
    input.style.width = '100%';
    input.style.boxSizing = 'border-box';

    // Create a unique datalist ID for this editor instance
    const listId = 'city-combo-' + Math.random().toString(36).substring(2);
    input.setAttribute('list', listId);

    const dataList = document.createElement('datalist');
    dataList.id = listId;

    // Get suggested values from params (passed from Python)
    const values = (params.cellEditorParams && params.cellEditorParams.values) || [];

    // Optional empty option so user can clear quickly
    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    dataList.appendChild(emptyOption);

    values.forEach(v => {
        const option = document.createElement('option');
        option.value = v;
        dataList.appendChild(option);
    });

    // Set initial value
    if (params.value != null) {
        input.value = params.value;
    }

    this.input = input;
    this.dataList = dataList;

    // Input lives inside the cell editor container
    this.container.appendChild(input);

    // IMPORTANT: put the datalist on document.body so the browser can always find it
    // (more robust than keeping it nested inside the cell)
    document.body.appendChild(dataList);
};

CityComboEditor.prototype.getGui = function() {
    return this.container;
};

CityComboEditor.prototype.afterGuiAttached = function() {
    if (this.input) {
        this.input.focus();
        this.input.select();

        // Try to immediately show the dropdown, like a real combo box
        if (typeof this.input.showPicker === 'function') {
            try {
                this.input.showPicker();
            } catch (err) {
                // Some browsers might not support or might throw; ignore
                console.warn('showPicker() not available:', err);
            }
        }
    }
};

CityComboEditor.prototype.getValue = function() {
    // Return final value from the input (may or may not be in the suggestions list)
    return this.input ? this.input.value : null;
};

CityComboEditor.prototype.destroy = function() {
    // Clean up datalist from the DOM
    if (this.dataList && this.dataList.parentNode) {
        this.dataList.parentNode.removeChild(this.dataList);
    }
    this.input = null;
    this.container = null;
    this.dataList = null;
};

CityComboEditor.prototype.isPopup = function() {
    // Inline editor (not a popup)
    return false;
};
</script>
"""
)


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

with ui.header().classes("py-2 px-4"):
    ui.label("NiceGUI AG Grid — Custom City Combo Editor")

ui.label(
    "Double-click a 'City' cell to edit. "
    "You get a dropdown of known cities, but can also type a new value."
).classes("mb-2")

# Column definitions:
# - Most columns non-editable.
# - "city" uses our custom CityComboEditor.
column_defs = [
    {"headerName": "ID", "field": "id", "editable": False},
    {"headerName": "Name", "field": "name", "editable": True},
    {"headerName": "Age", "field": "age", "editable": False},
    {
        "headerName": "City",
        "field": "city",
        "editable": True,
        # IMPORTANT: the colon prefix tells NiceGUI to treat the value as JS,
        # so this becomes cellEditor: CityComboEditor in the AG Grid options.
        ":cellEditor": "CityComboEditor",
        "cellEditorParams": {
            "values": unique_cities,
        },
    },
    {"headerName": "Score", "field": "score", "editable": False},
]

with ui.column().classes("w-full h-80 ag-theme-alpine"):
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


# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------

if __name__ in {"__main__", "__mp_main__"}:
    ui.run()
