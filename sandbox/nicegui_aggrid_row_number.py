# sandbox/nicegui_aggrid_row_number.py
from nicegui import ui

ROWS = [
    {"name": "Alice", "age": 34, "city": "Davis"},
    {"name": "Bob", "age": 28, "city": "Baltimore"},
    {"name": "Cleo", "age": 41, "city": "Boston"},
    {"name": "Drew", "age": 30, "city": "New York"},
    {"name": "Evan", "age": 25, "city": "Seattle"},
    {"name": "Fran", "age": 37, "city": "Chicago"},
    {"name": "Gina", "age": 29, "city": "San Francisco"},
    {"name": "Hugo", "age": 33, "city": "Philadelphia"},
    {"name": "Iris", "age": 26, "city": "Portland"},
    {"name": "Jude", "age": 45, "city": "Austin"},
    {"name": "Kara", "age": 31, "city": "Miami"},
    {"name": "Liam", "age": 39, "city": "Denver"},
]

@ui.page("/")
def index() -> None:
    ui.label("AG Grid row number column (#)").classes("text-lg font-semibold")

    grid_options = {
        "columnDefs": [
            # Row number column:
            # - valueGetter is a JS expression string
            # - node.rowIndex is the displayed row index (changes with sort/filter)
            {"headerName": "#", "valueGetter": "node.rowIndex + 1", "width": 70, "pinned": "left", "sortable": False, "filter": False},

            {"headerName": "Name", "field": "name", "sortable": True, "filter": True},
            {"headerName": "Age", "field": "age", "sortable": True, "filter": True, "width": 110},
            {"headerName": "City", "field": "city", "sortable": True, "filter": True},
        ],
        "rowData": ROWS,
        "defaultColDef": {"resizable": True},
        "rowSelection": {"mode": "singleRow", "enableClickSelection": True},
        "animateRows": True,
    }

    ui.aggrid(grid_options).classes("w-full h-96")

ui.run(reload=False)