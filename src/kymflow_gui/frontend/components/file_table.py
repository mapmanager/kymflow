from __future__ import annotations

from typing import Dict, List, Optional

from nicegui import ui

from kymflow_core.enums import SelectionOrigin
from kymflow_core.kym_file import KymFile
from kymflow_core.state import AppState


def _rows(files: List[KymFile]) -> List[Dict]:
    return [f.summary_row() for f in files]


def create_file_table(app_state: AppState) -> None:
    table = ui.table(
        rows=_rows(app_state.files),
        selection="single",
        row_key="path",
    ).classes("w-full")

    # Hide the 'path' column after table creation
    for column in table.columns:
        if column["name"] == "path":
            column["classes"] = "hidden"
            column["headerClasses"] = "hidden"
            table.update()
            break

    @app_state.file_list_changed.connect
    def _refresh() -> None:
        table.rows = _rows(app_state.files)

    def _on_select(event) -> None:
        selected = event.args.get("rows") or []
        if not selected:
            app_state.select_file(None, origin=SelectionOrigin.TABLE)
            return

        path = selected[0]["path"]
        match = next((f for f in app_state.files if str(f.path) == path), None)
        app_state.select_file(match, origin=SelectionOrigin.TABLE)

    table.on("selection", _on_select)

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
