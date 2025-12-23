from __future__ import annotations

from typing import Callable, Dict, List, Optional

from nicegui import ui, app

from kymflow.gui.events import SelectionOrigin
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui.state import AppState

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def _rows(files) -> List[Dict]:
    return [f.getRowDict() for f in files]


def create_file_table(
    app_state: AppState,
    *,
    selection_mode: str = "single",
    on_selection_change: Optional[Callable[[List[KymImage]], None]] = None,
    restore_selection: Optional[List[str]] = None,
) -> None:
    multi_select = selection_mode == "multiple"

    table = (
        ui.table(
            rows=_rows(app_state.files),
            selection=selection_mode,
            row_key="path",
        )
        .classes("w-full")
        .props("dense hide-selected-banner")
    )

    # Storage keys for per-user persistence
    storage_key = "file_selection_multi" if multi_select else "file_selection_single"

    # Track selections in memory for this page render
    selected_paths: set[str] = set() if multi_select else set()
    current_single: Optional[str] = None

    def _load_stored_selection() -> None:
        """Load stored selection from per-user storage."""
        nonlocal current_single, selected_paths
        stored = app.storage.user.get(storage_key)
        if multi_select:
            selected_paths.clear()
            if isinstance(stored, list):
                selected_paths.update(str(p) for p in stored)
        else:
            current_single = str(stored) if stored else None

    # Configure columns (column visibility will be handled in future aggrid migration)
    # Set width and alignment for narrow columns (checkmark columns)
    for column in table.columns:
        col_name = column["name"]
        if col_name in [
            "File Name",
            "Analyzed",
            "Saved",
            "Window Points",
            "pixels",
            "lines",
            "duration (s)",
            "ms/line",
            "um/pixel",
        ]:
            column["style"] = "width: 50px; min-width: 50px; max-width: 50px;"
            column["align"] = "center"
            table.update()

    def _restore_from_state() -> None:
        """Restore selection from storage-backed in-memory state."""
        if multi_select:
            if not selected_paths:
                return
            table.selected = [
                row for row in table.rows if row.get("path") in selected_paths
            ]
            if on_selection_change is not None:
                matches: List[KymImage] = []
                for path in selected_paths:
                    match = next(
                        (f for f in app_state.files if str(f.path) == path), None
                    )
                    if match:
                        matches.append(match)
                on_selection_change(matches)
        else:
            if not current_single:
                return
            match = next(
                (f for f in app_state.files if str(f.path) == current_single), None
            )
            if match:
                row = next(
                    (r for r in table.rows if r.get("path") == current_single), None
                )
                if row:
                    table.selected = [row]
                    app_state.select_file(match, origin=SelectionOrigin.TABLE)

    def _refresh() -> None:
        table.rows = _rows(app_state.files)
        if multi_select:
            table.selected = []
            selected_paths.clear()
            if on_selection_change is not None:
                on_selection_change([])
        else:
            table.selected = []
            current_single = None

        # Restore selection after refresh from stored state
        _restore_from_state()
    
    # Register callback (no decorator)
    app_state.on_file_list_changed(_refresh)

    def _on_select(event) -> None:
        nonlocal current_single
        rows_payload = event.args.get("rows")
        added_flag = event.args.get("added")

        # Normalize rows to a list of dicts
        rows: List[Dict] = rows_payload if isinstance(rows_payload, list) else []
        rows = [row for row in rows if isinstance(row, dict)]

        if multi_select:
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
                selected_paths.update(
                    {row.get("path") for row in rows if "path" in row}
                )

            # Sync visual selection to tracked set
            table.selected = [
                row for row in table.rows if row.get("path") in selected_paths
            ]

            if on_selection_change is not None:
                matches: List[KymImage] = []
                for path in selected_paths:
                    match = next(
                        (f for f in app_state.files if str(f.path) == path), None
                    )
                    if match:
                        matches.append(match)
                on_selection_change(matches)

            # Persist to per-user storage
            app.storage.user[storage_key] = list(selected_paths)
            return

        # single-select with manual toggle
        if not rows:
            table.selected = []
            current_single = None
            app.storage.user[storage_key] = None
            app_state.select_file(None, origin=SelectionOrigin.TABLE)
            return

        selected_path = rows[0].get("path")
        if current_single == selected_path:
            table.selected = []
            current_single = None
            app.storage.user[storage_key] = None
            app_state.select_file(None, origin=SelectionOrigin.TABLE)
            return

        match = next((f for f in app_state.files if str(f.path) == selected_path), None)
        app_state.select_file(match, origin=SelectionOrigin.TABLE)
        # Ensure table selection reflects the new choice
        table.selected = [row for row in table.rows if row.get("path") == selected_path]
        current_single = selected_path
        app.storage.user[storage_key] = selected_path

    table.on("selection", _on_select)

    if not multi_select:
        
        def _on_external_selection(
            kf: Optional[KymImage],
            origin: Optional[SelectionOrigin],
        ) -> None:
            if origin is SelectionOrigin.TABLE:
                return
            if not kf:
                table.selected = []
                current_single = None
                app.storage.user[storage_key] = None
                return

            row = next((r for r in table.rows if r["path"] == str(kf.path)), None)
            if row is None:
                table.selected = []
                current_single = None
                app.storage.user[storage_key] = None
                return
            table.selected = [row]
            current_single = row["path"]
            app.storage.user[storage_key] = row["path"]
        
        # Register callback (no decorator)
        app_state.on_selection_changed(_on_external_selection)

    # Initial restoration from session state (or optional restore_selection seed)
    if restore_selection:
        # Seed session state from provided paths
        if multi_select and selected_paths is not None:
            selected_paths.clear()
            selected_paths.update(restore_selection)
        elif not multi_select:
            current_single = restore_selection[0]
            app.storage.user[storage_key] = current_single
    _load_stored_selection()
    _restore_from_state()
