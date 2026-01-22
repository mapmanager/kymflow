# sandbox/folder_picker_aggrid_min.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from nicegui import ui


def ensure_aggrid_css() -> None:
    """Ensure AG Grid CSS is loaded.

    NiceGUI's ui.aggrid may not include AG Grid theme CSS in all setups.
    If the theme CSS is missing, the grid can appear blank even when rowData exists.

    We only inject <link> tags (no scripts) to keep this stable.
    """
    ui.add_head_html(
        """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ag-grid-community/styles/ag-grid.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ag-grid-community/styles/ag-theme-alpine.css">
        """.strip()
    )


def list_dir(path: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """List a directory as a list of dict rows (dirs first), safe against permission errors."""
    try:
        items = list(path.iterdir())
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

    items.sort(key=lambda p: (not p.is_dir(), p.name.lower()))
    rows: List[Dict[str, Any]] = []
    for p in items:
        rows.append(
            {
                "name": p.name,
                "kind": "dir" if p.is_dir() else ("file" if p.is_file() else "other"),
                "path": str(p),
            }
        )
    return rows, None


@ui.page("/")
def main() -> None:
    ensure_aggrid_css()

    state: Dict[str, Any] = {
        "cwd": Path.home().expanduser().resolve(),
        "selected_path": None,
    }

    ui.label("Folder picker (AG Grid minimal)").classes("text-h5")
    cwd_label = ui.label().classes("text-subtitle2")
    status_label = ui.label().classes("text-body2 text-grey-7")
    debug_label = ui.label().classes("text-caption text-grey-7")

    with ui.row().classes("gap-2 items-center"):
        btn_up = ui.button("Up").props("outline")
        btn_refresh = ui.button("Refresh").props("outline")

    # IMPORTANT:
    # AG Grid theme class must be on a container element.
    # We'll create a container div with ag-theme-alpine and put ui.aggrid inside it.
    with ui.element("div").classes("ag-theme-alpine w-full").style("height: 70vh; border: 1px solid #ddd;"):
        grid = ui.aggrid(
            {
                "columnDefs": [
                    {"headerName": "Name", "field": "name", "flex": 1},
                    {"headerName": "Type", "field": "kind", "width": 120},
                    {"headerName": "Path", "field": "path", "flex": 2},
                ],
                "defaultColDef": {"sortable": True, "filter": True, "resizable": True},
                "rowSelection": "single",
                "animateRows": False,
                "rowData": [],
            }
        ).classes("w-full").style("height: 100%;")

    def refresh() -> None:
        cwd: Path = state["cwd"]
        rows, err = list_dir(cwd)

        print(f"[list_rows] {cwd} -> {len(rows)} rows; first={[r['name'] for r in rows[:5]]}")

        cwd_label.text = f"Current: {cwd}"
        status_label.text = f"Selected: {state['selected_path']}" if state["selected_path"] else "Selected: (none)"

        if err:
            debug_label.text = f"ERROR listing dir: {err}"
        else:
            # On-page debug that confirms the data passed to AG Grid
            first = rows[0] if rows else None
            debug_label.text = f"rowData len={len(rows)}; first_row={json.dumps(first) if first else 'None'}"

        # THE CORE INJECTION STEP (keep it dead simple):
        grid.options["rowData"] = rows
        grid.update()

    def go_up() -> None:
        cwd: Path = state["cwd"]
        parent = cwd.parent
        if parent == cwd:
            return
        state["cwd"] = parent
        state["selected_path"] = None
        refresh()

    async def on_row_clicked(e: Any) -> None:
        data = (e.args or {}).get("data") or {}
        state["selected_path"] = data.get("path")
        print(f"[rowClicked] data={data}")
        status_label.text = f"Selected: {state['selected_path']}" if state["selected_path"] else "Selected: (none)"

    async def on_row_double_clicked(e: Any) -> None:
        data = (e.args or {}).get("data") or {}
        print(f"[rowDoubleClicked] data={data}")
        if data.get("kind") == "dir" and data.get("path"):
            state["cwd"] = Path(data["path"]).resolve()
            state["selected_path"] = None
            refresh()

    btn_up.on_click(go_up)
    btn_refresh.on_click(refresh)
    grid.on("rowClicked", on_row_clicked)
    grid.on("rowDoubleClicked", on_row_double_clicked)

    refresh()


ui.run()