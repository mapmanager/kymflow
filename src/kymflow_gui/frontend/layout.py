from __future__ import annotations

from pathlib import Path

from nicegui import ui

from kymflow_core.enums import ThemeMode
from kymflow_core.state import AppState, TaskState
from kymflow_core.utils.logging import get_logger

from .components.analysis_toolbar import create_analysis_toolbar
from .components.file_table import create_file_table
from .components.folder_selector import create_folder_selector
from .components.image_viewer import create_image_viewer
from .components.metadata_form import create_metadata_form
from .components.olympus_form import create_olympus_form
from .components.plot_viewer import create_plot_viewer
from .components.task_progress import create_task_progress

logger = get_logger(__name__)


def create_main_page(default_folder: Path) -> None:
    ui.page_title('KymFlow')

    app_state = AppState()
    task_state = TaskState()
    current_folder = {"path": default_folder.expanduser()}
    dark_mode = ui.dark_mode()
    dark_mode.value = True
    app_state.set_theme(ThemeMode.DARK)

    def _on_folder_changed(folder: Path) -> None:
        """Callback when folder is changed via folder selector."""
        app_state.load_folder(folder)

    def _update_theme_icon() -> None:
        icon = "light_mode" if dark_mode.value else "dark_mode"
        theme_button.props(f"icon={icon}")

    def _toggle_theme() -> None:
        dark_mode.value = not dark_mode.value
        _update_theme_icon()
        mode = ThemeMode.DARK if dark_mode.value else ThemeMode.LIGHT
        app_state.set_theme(mode)

    with ui.header().classes("items-center justify-between"):
        ui.label("Kymflow")
        with ui.row().classes("items-center gap-2"):
            ui.button("Home")
            ui.button("About")
            theme_button = ui.button(
                icon="light_mode" if dark_mode.value else "dark_mode",
                on_click=_toggle_theme,
            ).props("flat round dense text-color=white").tooltip("Toggle dark / light mode")
            _update_theme_icon()
            with ui.dropdown_button("Options", icon="menu"):
                ui.menu_item("Settings", on_click=lambda: ui.notify("Settings clicked"))
                ui.menu_item("Profile", on_click=lambda: ui.notify("Profile clicked"))
                ui.separator()
                ui.menu_item("Logout", on_click=lambda: ui.notify("Logout clicked"))

    with ui.column().classes("w-full p-4 gap-4"):
        folder_display = ui.label(f"Folder: {current_folder['path']}")
        create_folder_selector(
            current_folder=current_folder,
            folder_display=folder_display,
            on_folder_changed=_on_folder_changed,
        )

        if current_folder["path"].exists():
            _on_folder_changed(current_folder["path"])
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

        with ui.expansion("Image Viewer", value=True).classes("w-full"):
            create_image_viewer(app_state)
        
        with ui.expansion("Plot Viewer", value=True).classes("w-full"):
            create_plot_viewer(app_state)

        with ui.expansion("Metadata", value=True).classes("w-full"):
            with ui.element('div').classes('flex w-full gap-4 items-start'):
                with ui.card().classes('flex-1'):
                    create_metadata_form(app_state)

                with ui.card().classes('flex-1'):
                    create_olympus_form(app_state)
