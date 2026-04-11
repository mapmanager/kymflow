"""Reusable AG Grid table: single-row selection, no checkboxes, stable row ids.

Uses ``list[dict]`` row data only (no pandas). Options follow nicewidgets patterns:
``:getRowId`` for JS callbacks and AG Grid v32+ ``rowSelection`` object.

Column widths use AG Grid ``autoSizeStrategy: fitCellContents`` (see NiceGUI
:class:`nicegui.elements.aggrid.AgGrid` ``auto_size_columns`` which maps to
``fitGridWidth`` only). ``fitGridWidth`` is not used here so columns size from
cell/header content without hardcoded pixel widths.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, Literal

from nicegui import ui
from nicegui.events import GenericEventArguments


class MyFileTable:
    """``ui.aggrid`` wrapper with a configurable row-id field and selection callback.

    Rows must include ``row_id_field`` (default ``\"relative_path\"``) so AG Grid can
    assign stable ids via ``:getRowId`` (JavaScript callback, not a JSON string).
    """

    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        columns: list[tuple[str, str]],
        row_id_field: str = "relative_path",
        on_selected: Callable[[str, dict[str, Any]], None] | None = None,
        grid_height: str = "min(28rem, 50vh)",
        auto_size_strategy: Literal["fitCellContents", "fitGridWidth", "none"] = "fitCellContents",
    ) -> None:
        self._rows = rows
        self._columns = columns
        self._row_id_field = row_id_field
        self._on_selected = on_selected
        self._grid_height = grid_height
        self._auto_size_strategy = auto_size_strategy
        self._grid: ui.aggrid | None = None

    def _grid_options(self) -> dict[str, Any]:
        column_defs: list[dict[str, Any]] = []
        for field, header in self._columns:
            column_defs.append(
                {
                    "headerName": header,
                    "field": field,
                    "sortable": True,
                    "resizable": True,
                    "filter": True,
                    "checkboxSelection": False,
                    "headerCheckboxSelection": False,
                }
            )
        fid = self._row_id_field
        opts: dict[str, Any] = {
            "columnDefs": column_defs,
            "rowData": self._rows,
            "rowSelection": {
                "mode": "singleRow",
                "enableClickSelection": True,
                "checkboxes": False,
            },
            "animateRows": True,
            "defaultColDef": {
                "sortable": True,
                "resizable": True,
                "filter": True,
            },
        }
        # AG Grid v34+: auto-size without hardcoded widths (see also NiceGUI AgGrid.auto_size_columns).
        if self._auto_size_strategy == "fitCellContents":
            opts["autoSizeStrategy"] = {"type": "fitCellContents"}
        elif self._auto_size_strategy == "fitGridWidth":
            opts["autoSizeStrategy"] = {"type": "fitGridWidth"}
        # "none": omit autoSizeStrategy; columns use default widths
        # Colon prefix: NiceGUI passes this as a JavaScript function to AG Grid.
        opts[":getRowId"] = (
            f"(params) => params.data && String(params.data['{fid}'])"
        )
        return opts

    async def _handle_row_selected(self, e: GenericEventArguments) -> None:
        if self._on_selected is None:
            return
        args = e.args or {}
        data = args.get("data")
        if isinstance(data, dict):
            rid = data.get(self._row_id_field)
            if rid is not None:
                result = self._on_selected(str(rid), data)
                if inspect.isawaitable(result):
                    await result
            return
        row_id = args.get("rowId")
        if row_id is None:
            return
        key = str(row_id)
        for row in self._rows:
            if str(row.get(self._row_id_field)) == key:
                result = self._on_selected(key, row)
                if inspect.isawaitable(result):
                    await result
                return

    def render(self) -> ui.aggrid:
        """Build the grid in the current NiceGUI container.

        The grid gets a single explicit ``height`` so AG Grid manages scrolling internally
        (same pattern as ``sandbox/aggrid-wide/demo_aggrid_simple_v2.py``). Wrapping in
        ``ui.scroll_area`` would duplicate scrollbars with the grid body viewport.
        """
        # auto_size_columns=False so NiceGUI does not inject fitGridWidth over options.
        self._grid = ui.aggrid(
            self._grid_options(),
            auto_size_columns=False,
            theme="alpine",
        ).classes("w-full border rounded")
        self._grid.style(f"height: {self._grid_height}; width: 100%;")
        self._grid.on("rowSelected", self._handle_row_selected)
        self._grid.update()
        return self._grid
