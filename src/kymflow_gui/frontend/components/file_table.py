from __future__ import annotations

from typing import Callable, Dict, List, Optional

from nicegui import ui

from kymflow_core.enums import SelectionOrigin
from kymflow_core.kym_file import KymFile
from kymflow_core.state import AppState

from kymflow_core.utils.logging import get_logger

logger = get_logger(__name__)

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

    # Track current selection for manual toggle support in single-select mode
    current_selected_path = {"path": None}
    # Track multi-select selection paths explicitly
    selected_paths = set() if multi_select else None

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
            if selected_paths is not None:
                selected_paths.clear()
            if on_selection_change is not None:
                on_selection_change([])
        else:
            table.selected = []
            current_selected_path["path"] = None

    def _on_select(event) -> None:
        rows_payload = event.args.get("rows")
        added_flag = event.args.get("added")

        # Normalize rows to a list of dicts
        rows: List[Dict] = rows_payload if isinstance(rows_payload, list) else []
        rows = [row for row in rows if isinstance(row, dict)]

        if multi_select:
            if selected_paths is None:
                if on_selection_change is not None:
                    on_selection_change([])
                return

            # Quasar often sends a single row with an added flag (bool) to indicate toggle
            if len(rows) == 1 and isinstance(added_flag, bool):
                path = rows[0].get("path")
                if path is not None:
                    if added_flag:
                        selected_paths.add(path)
                    else:
                        selected_paths.discard(path)
            else:
                # Fallback: rebuild from rows payload
                selected_paths.clear()
                selected_paths.update({row.get("path") for row in rows if "path" in row})

            # Sync visual selection to tracked set
            table.selected = [row for row in table.rows if row.get("path") in selected_paths]

            if on_selection_change is not None:
                matches: List[KymFile] = []
                for path in selected_paths:
                    match = next((f for f in app_state.files if str(f.path) == path), None)
                    if match:
                        matches.append(match)
                on_selection_change(matches)
            return

        # single-select with manual toggle
        if not rows:
            table.selected = []
            current_selected_path["path"] = None
            app_state.select_file(None, origin=SelectionOrigin.TABLE)
            return

        selected_path = rows[0].get("path")
        if current_selected_path["path"] == selected_path:
            table.selected = []
            current_selected_path["path"] = None
            app_state.select_file(None, origin=SelectionOrigin.TABLE)
            return

        match = next((f for f in app_state.files if str(f.path) == selected_path), None)
        app_state.select_file(match, origin=SelectionOrigin.TABLE)
        # Ensure table selection reflects the new choice
        table.selected = [row for row in table.rows if row.get("path") == selected_path]
        current_selected_path["path"] = selected_path

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
                current_selected_path["path"] = None
                return

            row = next((r for r in table.rows if r["path"] == str(kf.path)), None)
            if row is None:
                table.selected = []
                current_selected_path["path"] = None
                return
            table.selected = [row]
            current_selected_path["path"] = row["path"]
