from __future__ import annotations

from typing import Dict, List, Optional

from nicegui import ui

from kymflow_core.enums import SelectionOrigin
from kymflow_core.kym_file import KymFile
from kymflow_core.state import AppState


def _rows(files: List[KymFile]) -> List[Dict]:
    return [
        {
            "filename": file.path.name,
            "path": str(file.path),
            "pixels": file.pixels_per_line or "-",
            "lines": file.num_lines or "-",
        }
        for file in files
    ]


def create_file_table(app_state: AppState) -> None:
    columns = [
        {"name": "filename", "label": "Filename", "field": "filename"},
        {"name": "path", "label": "Path", "field": "path"},
        {"name": "pixels", "label": "Pixels/Line", "field": "pixels"},
        {"name": "lines", "label": "Lines", "field": "lines"},
    ]

    table = ui.table(
        title="Files",
        columns=columns,
        rows=_rows(app_state.files),
        selection="single",
        row_key="path",
    ).classes("w-full")

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
