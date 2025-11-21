from __future__ import annotations

from typing import Callable, Dict, List, Optional

from nicegui import ui

from kymflow_core.enums import SelectionOrigin
from kymflow_core.kym_file import KymFile
from kymflow_core.state import AppState


def _rows(files: List[KymFile]) -> List[Dict]:
    return [f.summary_row() for f in files]


def create_file_table(
    app_state: AppState,
    *,
    selection_mode: str = "single",
    on_selection_change: Optional[Callable[[List[KymFile]], None]] = None,
) -> None:
    multi_select = selection_mode == "multiple"

    table = ui.table(
        rows=_rows(app_state.files),
        selection=selection_mode,
        row_key="path",
    ).classes("w-full").props("dense hide-selected-banner")

    # Get column visibility schema from backend (reuses existing form schemas)
    column_visibility = KymFile.table_column_schema()
    
    # Configure columns based on schema
    for column in table.columns:
        col_name = column["name"]
        
        # Check visibility from schema (defaults to True if not in schema)
        if not column_visibility.get(col_name, True):
            column["classes"] = "hidden"
            column["headerClasses"] = "hidden"
            table.update()
            continue
        
        # Set width and alignment for narrow columns (checkmark columns)
        if col_name in ['File Name', "Analyzed", "Saved", "Window Points", 'pixels', 'lines', 'duration (s)', 'ms/line', 'um/pixel']:
            column["style"] = "width: 50px; min-width: 50px; max-width: 50px;"
            column["align"] = "center"
            table.update()

    @app_state.file_list_changed.connect
    def _refresh() -> None:
        table.rows = _rows(app_state.files)
        if multi_select:
            table.selected = []
            if on_selection_change is not None:
                on_selection_change([])

    def _on_select(event) -> None:
        selected = event.args.get("rows") or []

        if multi_select:
            if on_selection_change is None:
                return
            matches: List[KymFile] = []
            for row in selected:
                match = next((f for f in app_state.files if str(f.path) == row["path"]), None)
                if match:
                    matches.append(match)
            on_selection_change(matches)
            return

        if not selected:
            app_state.select_file(None, origin=SelectionOrigin.TABLE)
            return

        path = selected[0]["path"]
        match = next((f for f in app_state.files if str(f.path) == path), None)
        app_state.select_file(match, origin=SelectionOrigin.TABLE)

    table.on("selection", _on_select)

    if not multi_select:
        @app_state.selection_changed.connect
        def _on_external_selection(
            kf: Optional[KymFile],
            origin: Optional[SelectionOrigin],
        ) -> None:
            if origin is SelectionOrigin.TABLE:
                return
            if not kf:
                table.selected = []
                return

            row = next((r for r in table.rows if r["path"] == str(kf.path)), None)
            if row is None:
                table.selected = []
                return
            table.selected = [row]
