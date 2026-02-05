from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from nicegui import ui

from local_file_picker import local_file_picker


def _home_dir() -> str:
    return str(Path.home())


def _format_paths(paths: Optional[List[str]]) -> str:
    if not paths:
        return "(none)"
    return "\n".join(paths)


def build_ui() -> None:
    ui.page_title("Local File Picker Demo")

    ui.label("Local File Picker Demo (AG Grid)").classes("text-xl font-semibold")
    ui.label(
        "Buttons below show two modes:\n"
        "• Pick folder: OK returns folder path\n"
        "• Pick file(s): OK returns file path(s)\n"
        "Double-click navigates into folders; double-click on a file submits immediately."
    ).classes("text-sm text-gray-600 whitespace-pre-line")

    last_result = ui.label("Last result:\n(none)").classes("whitespace-pre-line font-mono text-sm mt-4")

    # this is the path picker we want
    async def pick_file_or_folder() -> None:
        start_dir = _home_dir()
        dlg = local_file_picker(
            start_dir,
            multiple=False,
            allow_folder_selection=True,  # ✅ folder OK is allowed
            show_hidden_files=False,
            upper_limit=None,  # allow navigation up; set to start_dir to “lock” at/under start_dir
        )
        result = await dlg
        # result is a list[str] or None
        last_result.text = f"Last result (Pick folder):\n{_format_paths(result)}"
        print("[DEBUG] pick_folder result:", result)

    # limit to just files - do not use
    async def pick_files() -> None:
        start_dir = _home_dir()
        dlg = local_file_picker(
            start_dir,
            multiple=True,               # ✅ allow multi-select
            allow_folder_selection=False, # ✅ folders ignored by OK (but double-click still navigates)
            show_hidden_files=False,
            upper_limit=None,
        )
        result = await dlg
        last_result.text = f"Last result (Pick file(s)):\n{_format_paths(result)}"
        print("[DEBUG] pick_files result:", result)

    with ui.row().classes("gap-3 mt-4"):
        ui.button("Pick file or folder", on_click=pick_file_or_folder)
        ui.button("Pick file(s)", on_click=pick_files).props("outline")

    ui.separator().classes("my-6")
    ui.label("Tip: set upper_limit=start_dir to prevent navigating above the start folder.").classes(
        "text-xs text-gray-500"
    )


build_ui()
ui.run()