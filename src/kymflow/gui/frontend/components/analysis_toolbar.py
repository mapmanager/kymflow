from __future__ import annotations

from nicegui import ui

from kymflow.gui.state import AppState
from kymflow.core.state import TaskState
from kymflow.gui.tasks import run_flow_analysis

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def create_analysis_toolbar(app_state: AppState, task_state: TaskState) -> None:
    with ui.row().classes("items-end gap-2"):
        ui.label("Analysis").classes("text-lg font-semibold")
        window_input = ui.select(
            options=[16, 32, 64, 128, 256],
            value=16,
            label="Window Points",
        ).classes("w-32")
        start_button = ui.button("Analyze Flow")
        cancel_button = ui.button("Cancel", on_click=task_state.request_cancel)
        cancel_button.disabled = True

    def _on_run() -> None:
        logger.warning("")

        kf = app_state.selected_file
        if not kf:
            ui.notify("Select a file first", color="warning")
            return
        
        # Require ROI selection before starting analysis
        if app_state.selected_roi_id is None:
            ui.notify("Select an ROI first", color="warning")
            return
        
        window_value = window_input.value
        window = int(window_value)

        # Immediate UI feedback before the worker thread toggles state
        start_button.disable()

        def _after_result(_success: bool) -> None:
            app_state.update_metadata(kf)
            app_state.refresh_file_rows()

        run_flow_analysis(
            kf,
            task_state,
            window_size=window,
            roi_id=app_state.selected_roi_id,
            on_result=_after_result,
        )

    start_button.on("click", _on_run)

    # Sync buttons based on task state; keep it on the UI thread via timer polling
    def _sync_buttons() -> None:
        running = task_state.running
        cancellable = task_state.cancellable
        has_file = app_state.selected_file is not None
        has_roi = app_state.selected_roi_id is not None
        
        # Start button: enabled when not running, file selected, and ROI selected
        if running or not has_file or not has_roi:
            start_button.disable()
            if running:
                start_button.props("color=red")
            else:
                start_button.props(remove="color")
        else:
            start_button.enable()
            start_button.props(remove="color")

        # Cancel button: enabled only when running and cancellable
        if running and cancellable:
            cancel_button.enable()
            cancel_button.props("color=red")
        else:
            cancel_button.disable()
            cancel_button.props(remove="color")

    _sync_buttons()
    ui.timer(0.2, _sync_buttons)
