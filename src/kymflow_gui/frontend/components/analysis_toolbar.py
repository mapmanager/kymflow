from __future__ import annotations

from nicegui import ui

from kymflow_core.state import AppState, TaskState
from kymflow_core.tasks import run_flow_analysis

from .button_utils import sync_cancel_button


def create_analysis_toolbar(app_state: AppState, task_state: TaskState) -> None:
    
    with ui.row().classes("items-end gap-2"):
        ui.label("Analysis").classes("text-lg font-semibold")
        window_input = ui.select(
            options=[16, 32, 64, 128, 256],
            value=16,
            label="Window Points",
        ).classes("w-32")
        start_button = ui.button("Run analysis")
        cancel_button = ui.button("Cancel", on_click=task_state.request_cancel)
        cancel_button.disabled = True

    def _on_run() -> None:
        kf = app_state.selected_file
        if not kf:
            ui.notify("Select a file first", color="warning")
            return
        window_value = window_input.value
        window = int(window_value)

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

    # Set initial disabled state and color for start button
    def _update_start_button_state() -> None:
        running = task_state.running
        start_button.disabled = running
        # Set red color when running (disabled) to verify button is actually disabled
        if running:
            start_button.props("color=red")
        else:
            start_button.props(remove="color")
    
    _update_start_button_state()
    
    # Connect start button to task state changes (match task_progress.py pattern)
    @task_state.events.running.connect  # type: ignore[attr-defined]
    def _on_running_changed() -> None:
        _update_start_button_state()
    
    # Use button_utils for cancel button (it works, so keep it)
    sync_cancel_button(cancel_button, task_state, red_when_running=True)
