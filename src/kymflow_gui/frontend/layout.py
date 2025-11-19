from __future__ import annotations

from pathlib import Path
from typing import Optional

from nicegui import ui

from kymflow_core.state import AppState, TaskState
from kymflow_core.utils.logging import get_logger

from .components.analysis_toolbar import create_analysis_toolbar
from .components.file_table import create_file_table
from .components.image_viewer import create_image_viewer
from .components.metadata_form import create_metadata_form
from .components.plot_viewer import create_plot_viewer
from .components.task_progress import create_task_progress

logger = get_logger(__name__)


def create_main_page(default_folder: Path) -> None:
    app_state = AppState()
    task_state = TaskState()
    current_folder = {"path": default_folder.expanduser()}

    def _load_folder(path_str: str) -> None:
        folder = Path(path_str).expanduser()
        if not folder.exists():
            ui.notify(f"Folder not found: {folder}", color="negative")
            return
        logger.info("Loading folder %s", folder)
        app_state.load_folder(folder)
        current_folder["path"] = folder
        folder_display.set_text(f"Folder: {folder}")

    def _prompt_for_directory(initial: Path) -> Optional[str]:
        try:
            import tkinter as tk  # type: ignore
            from tkinter import filedialog
        except Exception as exc:  # pragma: no cover - platform specifics
            logger.warning("Folder dialog unavailable: %s", exc)
            ui.notify("Folder picker unavailable", color="negative")
            return None

        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selection = filedialog.askdirectory(initialdir=str(initial))
        except Exception as exc:  # pragma: no cover - user environment
            logger.warning("Folder dialog failed: %s", exc)
            ui.notify("Could not open folder picker", color="negative")
            return None
        finally:
            if root is not None:
                root.destroy()
        return selection or None

    def _choose_folder() -> None:
        initial = current_folder["path"]
        selection = _prompt_for_directory(initial)
        if selection:
            _load_folder(selection)

    with ui.header().classes("items-center justify-between"):
        ui.label("Kymflow")
        with ui.row():
            ui.button("Home")
            ui.button("About")
            with ui.dropdown_button("Options", icon="menu"):
                ui.menu_item("Settings", on_click=lambda: ui.notify("Settings clicked"))
                ui.menu_item("Profile", on_click=lambda: ui.notify("Profile clicked"))
                ui.separator()
                ui.menu_item("Logout", on_click=lambda: ui.notify("Logout clicked"))

    with ui.column().classes("w-full p-4 gap-4"):
        folder_row = ui.row().classes("w-full items-end gap-2")
        with folder_row:
            ui.button("Choose folder", on_click=_choose_folder)
            ui.button(
                "Reload",
                on_click=lambda: _load_folder(str(current_folder["path"]))
            )
            folder_display = ui.label(f"Folder: {current_folder['path']}")

        if current_folder["path"].exists():
            _load_folder(str(current_folder["path"]))
        else:
            ui.notify(
                f"Default folder missing: {current_folder['path']}",
                color="warning",
            )

        with ui.row().classes("w-full items-start gap-4"):
            with ui.column().classes("flex-1 gap-2"):
                create_analysis_toolbar(app_state, task_state)
            with ui.column().classes("shrink gap-2"):
                create_task_progress(task_state)

        with ui.expansion("Files", value=True).classes("w-full"):
            create_file_table(app_state)

        with ui.row().classes("w-full gap-4"):
            with ui.column().classes("w-2/3 gap-4"):
                with ui.expansion("Image Viewer", value=True).classes("w-full"):
                    create_image_viewer(app_state)
                with ui.expansion("Plot Viewer", value=True).classes("w-full"):
                    create_plot_viewer(app_state)
            with ui.column().classes("w-1/3 gap-4"):
                with ui.expansion("Metadata", value=True).classes("w-full"):
                    create_metadata_form(app_state)
