from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import List

from nicegui import ui, app

from kymflow_core.enums import ThemeMode
from kymflow_core.kym_file import KymFile
from kymflow_core.state import AppState, TaskState
from kymflow_core.tasks import run_batch_flow_analysis
from kymflow_core.utils.logging import get_log_file_path, get_logger

from .components.analysis_form import create_analysis_form
from .components.analysis_toolbar import create_analysis_toolbar
from .components.button_utils import sync_cancel_button
from .components.contrast_widget import create_contrast_widget
from .components.file_table import create_file_table
from .components.folder_selector import create_folder_selector
from .components.image_line_viewer import create_image_line_viewer
from .components.metadata_form import create_metadata_form
from .components.olympus_form import create_olympus_form
from .components.save_buttons import create_save_buttons
from .components.task_progress import create_task_progress

logger = get_logger(__name__)

def open_external(url: str) -> None:
    """Open a URL in the system browser (native) or new tab (browser)."""
    # Heuristic: in native mode, a main_window is created
    native = getattr(app, "native", None)
    in_native = getattr(native, "main_window", None) is not None

    if in_native:
        # Native desktop app: open in system browser
        webbrowser.open(url)
    else:
        # Browser mode: open in new tab
        ui.run_javascript(f'window.open("{url}", "_blank")')
        
def _inject_global_styles() -> None:
    """Add shared CSS tweaks for NiceGUI components."""
    ui.add_head_html(
        """
<style>
.q-expansion-item__container .q-item {
    flex-direction: row-reverse;
}
.q-expansion-item__container .q-item__section--main {
    text-align: left;
}
</style>
"""
    )


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
        # Left side: Title and navigation buttons
        with ui.row().classes("items-center gap-4"):
            ui.label("KymFlow").classes("text-2xl font-bold text-white")
            home_button = ui.button(
                "Home",
                on_click=lambda: _navigate("/"),
            ).props("flat text-color=white")

            batch_button = ui.button(
                "Batch",
                on_click=lambda: _navigate("/batch"),
            ).props("flat text-color=white")

            about_button = ui.button(
                "About",
                on_click=lambda: _navigate("/about"),
            ).props("flat text-color=white")

            if current_page == "home":
                home_button.disable()
            if current_page == "batch":
                batch_button.disable()
            if current_page == "about":
                about_button.disable()

        # Right side: Documentation, GitHub and theme buttons
        with ui.row().classes("items-center gap-2"):
            # Documentation "button" as a clickable icon
            docs_icon = ui.button(
                icon="menu_book",
                on_click=lambda _: open_external("https://mapmanager.github.io/kymflow/"),
            ).props("flat round dense text-color=white").tooltip("Open documentation")
            
            # GitHub "button" as a clickable image (no background)
            github_icon = ui.image(
                "https://cdn.simpleicons.org/github/ffffff"
            ).classes("w-6 h-6 cursor-pointer")

            github_icon.on(
                "click",
                lambda _: open_external("https://github.com/mapmanager/kymflow"),
            )

            github_icon.tooltip("Open GitHub repository")

            theme_button = ui.button(
                icon="light_mode" if dark_mode.value else "dark_mode",
                on_click=_toggle_theme,
            ).props("flat round dense text-color=white").tooltip("Toggle dark / light mode")
            _update_theme_icon()


def create_main_page(default_folder: Path) -> None:
    ui.page_title('KymFlow')
    _inject_global_styles()

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
        create_folder_selector(
            current_folder=current_folder,
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
                create_save_buttons(app_state, task_state)

        with ui.expansion("Files", value=True).classes("w-full"):
            # Retrieve stored selection for home page
            stored_selection = app.storage.browser.get('home_selection_path', None)
            restore_selection = [stored_selection] if stored_selection else None
            create_file_table(app_state, restore_selection=restore_selection)

        with ui.expansion("Contrast Controls", value=False).classes("w-full"):
            create_contrast_widget(app_state)

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
    _inject_global_styles()

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
        create_folder_selector(
            current_folder=current_folder,
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
                with ui.card().classes("w-full gap-4 p-4"):
                    with ui.row().classes("items-center gap-2 w-full"):
                        ui.label("Batch controls").classes("text-lg font-semibold")
                        window_select = ui.select(
                            options=[16, 32, 64, 128, 256],
                            value=16,
                            label="Window Points",
                        ).classes("w-32")
                        analyze_selected_button = ui.button(
                            "Analyze Flow",
                            on_click=lambda: _start_batch(True),
                        )
                        cancel_button = ui.button("Cancel", on_click=per_file_task.request_cancel)
                        cancel_button.disabled = True
            with ui.column().classes("shrink gap-2"):
                create_save_buttons(app_state, per_file_task)

        selected_label = ui.label("Selected: 0 files").classes("text-sm text-gray-400")

        def _update_selection(files: List[KymFile]) -> None:
            selected_files["files"] = files
            selected_label.set_text(f"Selected: {len(files)} file(s)")

        # Initialize selection state before the table renders and fires callbacks
        _update_selection([])

        with ui.expansion("Files", value=True).classes("w-full"):
            # Retrieve stored selection for batch page
            stored_selection = app.storage.browser.get('batch_selection_paths', [])
            restore_selection = stored_selection if isinstance(stored_selection, list) else []
            create_file_table(
                app_state,
                selection_mode="multiple",
                on_selection_change=_update_selection,
                restore_selection=restore_selection,
            )

        with ui.row().classes("w-full gap-4"):
            with ui.card().classes("flex-1 gap-2 p-4"):
                ui.label("Across files").classes("font-semibold")
                create_task_progress(overall_task)
            with ui.card().classes("flex-1 gap-2 p-4"):
                ui.label("Within file").classes("font-semibold")
                create_task_progress(per_file_task)

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

    _update_selection([])
    
    # Set initial disabled state and color for analyze button
    def _update_analyze_button_state() -> None:
        running = per_file_task.running
        analyze_selected_button.disabled = running
        # Set red color when running (disabled) to verify button is actually disabled
        if running:
            analyze_selected_button.props("color=red")
        else:
            analyze_selected_button.props(remove="color")
    
    _update_analyze_button_state()
    
    # Connect analyze button to task state changes (match task_progress.py pattern)
    @per_file_task.events.running.connect  # type: ignore[attr-defined]
    def _on_running_changed() -> None:
        _update_analyze_button_state()
    
    # Use button_utils for cancel button (it works, so keep it)
    sync_cancel_button(cancel_button, per_file_task, red_when_running=True)


def create_about_page(version_info: dict[str, str]) -> None:
    """Render the About page with version/build information."""
    ui.page_title('KymFlow - About')
    _inject_global_styles()

    app_state = AppState()
    dark_mode = ui.dark_mode()
    dark_mode.value = True
    app_state.set_theme(ThemeMode.DARK)

    _build_header(app_state, dark_mode, current_page="about")

    with ui.column().classes("w-full p-4 gap-4"):
        ui.label("Welcome to KymFlow").classes("text-2xl font-bold")
        with ui.card().classes("w-full p-4 gap-2"):
            ui.label("Version info").classes("text-lg font-semibold")
            for key, value in version_info.items():
                with ui.row().classes("items-center gap-2"):
                    ui.label(f"{key}:").classes("text-sm text-gray-500")
                    ui.label(str(value)).classes("text-sm")

        # Log file viewer
        log_path = get_log_file_path()

        max_lines = 300
        log_content = ""
        if log_path and log_path.exists():
            try:
                from collections import deque
                with log_path.open("r", encoding="utf-8", errors="replace") as f:
                    tail_lines = deque(f, maxlen=max_lines)
                log_content = "".join(tail_lines)
                if len(tail_lines) == max_lines:
                    log_content = f"...(truncated, last {max_lines} lines)...\n{log_content}"
            except Exception as e:
                log_content = f"Unable to read log file: {e}"
                
        with ui.expansion("Logs", value=False).classes("w-full"):
            ui.label(f"Log file: {log_path or 'N/A'}").classes("text-sm text-gray-500")
            ui.code(log_content or "[empty]").classes("w-full text-sm").style(
                "white-space: pre-wrap; font-family: monospace; max-height: 400px; overflow: auto;"
            )
