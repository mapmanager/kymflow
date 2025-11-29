from __future__ import annotations

from nicegui import ui

from kymflow_core.state import AppState, TaskState
from kymflow_core.tasks import run_flow_analysis

from kymflow_core.utils.logging import get_logger

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
        logger.warning('')

        kf = app_state.selected_file
        if not kf:
            ui.notify("Select a file first", color="warning")
            return
        window_value = window_input.value
        window = int(window_value)

        # Immediate UI feedback before the worker thread toggles state
        start_button.disable()

        def _after_result(_success: bool) -> None:
            app_state.notify_metadata_changed(kf)
            app_state.refresh_file_rows()

        run_flow_analysis(
            kf,
            task_state,
            window_size=window,
            on_result=_after_result,
        )

    start_button.on("click", _on_run)

    # Sync buttons based on task state; keep it on the UI thread via timer polling
    def _sync_buttons() -> None:
        running = task_state.running
        cancellable = task_state.cancellable
        if running:
            start_button.disable()
        else:
            start_button.enable()

        if running and cancellable:
            cancel_button.enable()
        else:
            cancel_button.disable()

        if running:
            start_button.props("color=red")
            cancel_button.props("color=red")
        else:
            start_button.props(remove="color")
            cancel_button.props(remove="color")

    _sync_buttons()
    ui.timer(0.2, _sync_buttons)
