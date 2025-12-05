"""Batch page content builder."""

from __future__ import annotations

from pathlib import Path
from typing import List

from nicegui import ui, app

from kymflow.gui.app_context import AppContext
from kymflow.core.kym_file import KymFile
from kymflow.gui.tasks import run_batch_flow_analysis
from kymflow.gui.frontend.components.folder_selector import create_folder_selector
from kymflow.gui.frontend.components.file_table import create_file_table
from kymflow.gui.frontend.components.task_progress import create_task_progress
from kymflow.gui.frontend.components.save_buttons import create_save_buttons
from kymflow.gui.frontend.components.button_utils import sync_cancel_button


def build_batch_content(context: AppContext) -> None:
    """Build the Batch page content.
    
    Provides multi-file batch analysis workflow with:
    - Folder selection and browsing
    - File list with multi-selection
    - Batch analysis controls
    - Dual progress tracking (across files + within file)
    
    Args:
        context: Application context with shared state
    """
    # Track current folder and selected files for this page load
    current_folder = {"path": context.default_folder}
    selected_files: dict[str, List[KymFile]] = {"files": []}
    
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
    
    # Batch controls and save buttons
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
                    
                    def _start_batch(selected_only: bool) -> None:
                        """Start batch analysis."""
                        if context.batch_task.running:
                            ui.notify("Batch already running", color="warning")
                            return
                        
                        files = selected_files["files"] if selected_only else list(context.app_state.files)
                        if not files:
                            ui.notify("No files to analyze", color="warning")
                            return
                        
                        window_value = int(window_select.value or 16)
                        
                        run_batch_flow_analysis(
                            files,
                            context.batch_task,
                            context.batch_overall_task,
                            window_size=window_value,
                            on_file_complete=lambda _kf: context.app_state.refresh_file_rows(),
                            on_batch_complete=lambda _cancelled: context.app_state.refresh_file_rows(),
                        )
                    
                    analyze_selected_button = ui.button(
                        "Analyze Flow",
                        on_click=lambda: _start_batch(True),
                    )
                    cancel_button = ui.button(
                        "Cancel", on_click=context.batch_task.request_cancel
                    )
                    cancel_button.disabled = True
        with ui.column().classes("shrink gap-2"):
            create_save_buttons(context.app_state, context.batch_task)
    
    # Selection label
    selected_label = ui.label("Selected: 0 files").classes("text-sm text-gray-400")
    
    def _update_selection(files: List[KymFile]) -> None:
        selected_files["files"] = files
        selected_label.set_text(f"Selected: {len(files)} file(s)")
    
    # Initialize selection state
    _update_selection([])
    
    # File table with multi-selection
    with ui.expansion("Files", value=True).classes("w-full"):
        stored_selection = app.storage.browser.get("batch_selection_paths", [])
        restore_selection = (
            stored_selection if isinstance(stored_selection, list) else []
        )
        create_file_table(
            context.app_state,
            selection_mode="multiple",
            on_selection_change=_update_selection,
            restore_selection=restore_selection,
        )
    
    # Progress indicators
    with ui.row().classes("w-full gap-4"):
        with ui.card().classes("flex-1 gap-2 p-4"):
            ui.label("Across files").classes("font-semibold")
            create_task_progress(context.batch_overall_task)
        with ui.card().classes("flex-1 gap-2 p-4"):
            ui.label("Within file").classes("font-semibold")
            create_task_progress(context.batch_task)
    
    # Button state synchronization
    # NOTE: Removed signal connection to avoid "deleted client" errors.
    # Initial state is set here; button_utils.sync_cancel_button handles updates.
    analyze_selected_button.disabled = context.batch_task.running
    
    # Sync cancel button (this utility handles the lifecycle properly)
    sync_cancel_button(cancel_button, context.batch_task, red_when_running=True)
