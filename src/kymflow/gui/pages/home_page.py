"""Home page content builder."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui, app

from kymflow.gui.app_context import AppContext
from kymflow.gui.frontend.components.folder_selector import create_folder_selector
from kymflow.gui.frontend.components.file_table import create_file_table
from kymflow.gui.frontend.components.analysis_toolbar import create_analysis_toolbar
from kymflow.gui.frontend.components.task_progress import create_task_progress
from kymflow.gui.frontend.components.save_buttons import create_save_buttons
from kymflow.gui.frontend.components.contrast_widget import create_contrast_widget
from kymflow.gui.frontend.components.image_line_viewer import create_image_line_viewer
from kymflow.gui.frontend.components.metadata_form import create_metadata_form
from kymflow.gui.frontend.components.olympus_form import create_olympus_form
from kymflow.gui.frontend.components.analysis_form import create_analysis_form


def build_home_content(context: AppContext) -> None:
    """Build the Home page content.
    
    Provides single file analysis workflow with:
    - Folder selection and browsing
    - File list with single selection
    - Image viewing and contrast controls
    - Metadata editing
    
    Args:
        context: Application context with shared state
    """
    # Track current folder for this page load
    current_folder = {"path": context.default_folder}
    
    def _on_folder_changed(folder: Path) -> None:
        """Callback when folder is changed via folder selector."""
        context.app_state.load_folder(folder, depth=context.app_state.folder_depth)
        current_folder["path"] = folder
    
    # Folder selector
    create_folder_selector(
        current_folder=current_folder,
        on_folder_changed=_on_folder_changed,
        app_state=context.app_state,
    )
    
    # Initialize folder only if not already loaded
    if current_folder["path"].exists():
        if context.app_state.folder is None:
            _on_folder_changed(current_folder["path"])
    else:
        ui.notify(
            f"Default folder missing: {current_folder['path']}",
            color="warning",
        )
    
    # Analysis toolbar, progress, and save buttons
    with ui.row().classes("w-full items-start gap-4"):
        with ui.column().classes("flex-1 gap-2"):
            create_analysis_toolbar(context.app_state, context.home_task)
        with ui.column().classes("shrink gap-2"):
            create_task_progress(context.home_task)
        with ui.column().classes("shrink gap-2"):
            create_save_buttons(context.app_state, context.home_task)
    
    # File table with stored selection restoration
    with ui.expansion("Files", value=True).classes("w-full"):
        stored_selection = app.storage.browser.get("home_selection_path", None)
        restore_selection = [stored_selection] if stored_selection else None
        create_file_table(context.app_state, restore_selection=restore_selection)
    
    # Contrast controls
    with ui.expansion("Contrast Controls", value=False).classes("w-full"):
        create_contrast_widget(context.app_state)
    
    # Image and line viewer
    with ui.expansion("Image & Line Viewer", value=True).classes("w-full"):
        create_image_line_viewer(context.app_state)
    
    # Metadata forms
    with ui.expansion("Metadata", value=True).classes("w-full"):
        with ui.element("div").classes("flex w-full gap-4 items-start"):
            with ui.card().classes("flex-1"):
                create_metadata_form(context.app_state)
            
            with ui.card().classes("flex-1"):
                create_olympus_form(context.app_state)
            
            with ui.card().classes("flex-1"):
                create_analysis_form(context.app_state)
