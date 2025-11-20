from __future__ import annotations

from pathlib import Path
from typing import List

from nicegui import ui

from kymflow_core.enums import ThemeMode
from kymflow_core.kym_file import KymFile
from kymflow_core.state import AppState, TaskState
from kymflow_core.tasks import run_batch_flow_analysis
from kymflow_core.utils.logging import get_logger

from .components.analysis_form import create_analysis_form
from .components.analysis_toolbar import create_analysis_toolbar
from .components.file_table import create_file_table
from .components.folder_selector import create_folder_selector
from .components.image_line_viewer import create_image_line_viewer
from .components.metadata_form import create_metadata_form
from .components.olympus_form import create_olympus_form
from .components.save_buttons import create_save_buttons
from .components.task_progress import create_task_progress

logger = get_logger(__name__)


def _build_header(app_state: AppState, dark_mode, current_page: str) -> None:

    def _navigate(path: str) -> None:
        ui.run_javascript(f'window.location.href="{path}"')

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
            home_button = ui.button(
                "Home",
                on_click=lambda: _navigate("/"),
            ).props("flat text-color=white")
            batch_button = ui.button(
                "Batch",
                on_click=lambda: _navigate("/batch"),
            ).props("flat text-color=white")
            if current_page == "home":
                home_button.disable()
            if current_page == "batch":
                batch_button.disable()

            ui.button("About").props("flat text-color=white")

            github_button = ui.button(
                on_click=lambda: ui.run_javascript(
                    'window.open("https://github.com/mapmanager/kymflow", "_blank")'
                ),
            ).props('flat round dense')
            with github_button:
                ui.icon('i-mdi-github').classes('text-white text-lg')
            github_button.tooltip('Open GitHub repository')

            theme_button = ui.button(
                icon="light_mode" if dark_mode.value else "dark_mode",
                on_click=_toggle_theme,
            ).props("flat round dense text-color=white").tooltip("Toggle dark / light mode")
            _update_theme_icon()


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

    _build_header(app_state, dark_mode, current_page="home")

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
            with ui.column().classes("shrink gap-2"):
                create_save_buttons(app_state)

        with ui.expansion("Files", value=True).classes("w-full"):
            create_file_table(app_state)

        with ui.expansion("Image & Line Viewer", value=True).classes("w-full"):
            create_image_line_viewer(app_state)

        with ui.expansion("Metadata", value=True).classes("w-full"):
            with ui.element('div').classes('flex w-full gap-4 items-start'):
                with ui.card().classes('flex-1'):
                    create_metadata_form(app_state)

                with ui.card().classes('flex-1'):
                    create_olympus_form(app_state)

                with ui.card().classes('flex-1'):
                    create_analysis_form(app_state)


def create_batch_page(default_folder: Path) -> None:
    ui.page_title('KymFlow - Batch Analysis')

    app_state = AppState()
    per_file_task = TaskState()
    overall_task = TaskState()
    current_folder = {"path": default_folder.expanduser()}
    selected_files: dict[str, List[KymFile]] = {"files": []}
    dark_mode = ui.dark_mode()
    dark_mode.value = True
    app_state.set_theme(ThemeMode.DARK)

    def _on_folder_changed(folder: Path) -> None:
        app_state.load_folder(folder)

    _build_header(app_state, dark_mode, current_page="batch")

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

        with ui.card().classes("w-full gap-4 p-4"):
            ui.label("Batch controls").classes("text-lg font-semibold")
            window_select = ui.select(
                options=[16, 32, 64, 128, 256],
                value=16,
                label="Window size",
            ).classes("w-32")
            with ui.row().classes("gap-2"):
                analyze_selected_button = ui.button(
                    "Analyze selected",
                    on_click=lambda: _start_batch(True),
                )
                analyze_all_button = ui.button(
                    "Analyze all",
                    on_click=lambda: _start_batch(False),
                )
                cancel_button = ui.button("Cancel", on_click=per_file_task.request_cancel)
                cancel_button.visible = False

        selected_label = ui.label("Selected: 0 files").classes("text-sm text-gray-400")

        with ui.expansion("Files", value=True).classes("w-full"):
            create_file_table(
                app_state,
                selection_mode="multiple",
                on_selection_change=lambda files: _update_selection(files),
            )

        with ui.row().classes("w-full gap-4"):
            with ui.card().classes("flex-1 gap-2 p-4"):
                ui.label("Across files").classes("font-semibold")
                create_task_progress(overall_task)
            with ui.card().classes("flex-1 gap-2 p-4"):
                ui.label("Within file").classes("font-semibold")
                create_task_progress(per_file_task)

    def _update_selection(files: List[KymFile]) -> None:
        selected_files["files"] = files
        selected_label.set_text(f"Selected: {len(files)} file(s)")

    def _start_batch(selected_only: bool) -> None:
        if per_file_task.running:
            ui.notify("Batch already running", color="warning")
            return

        files = selected_files["files"] if selected_only else list(app_state.files)
        if not files:
            ui.notify("No files to analyze", color="warning")
            return

        window_value = int(window_select.value or 16)

        run_batch_flow_analysis(
            files,
            per_file_task,
            overall_task,
            window_size=window_value,
            on_file_complete=lambda _kf: app_state.refresh_file_rows(),
            on_batch_complete=lambda _cancelled: app_state.refresh_file_rows(),
        )

    def _sync_buttons() -> None:
        running = per_file_task.running
        analyze_selected_button.disabled = running
        analyze_all_button.disabled = running
        cancel_button.visible = running and per_file_task.cancellable

    _update_selection([])
    _sync_buttons()

    @per_file_task.events.running.connect  # type: ignore[attr-defined]
    def _on_running_changed() -> None:
        _sync_buttons()
