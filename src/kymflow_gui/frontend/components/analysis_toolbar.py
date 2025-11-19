from __future__ import annotations

from nicegui import ui

from kymflow_core.state import AppState, TaskState
from kymflow_core.tasks import run_flow_analysis


def create_analysis_toolbar(app_state: AppState, task_state: TaskState) -> None:
    
    with ui.row().classes("items-end gap-2"):
        ui.label("Analysis").classes("text-lg font-semibold")
        window_input = ui.select(
            options=[16, 32, 64, 128, 256],
            value=16,
            label="Window size",
        ).classes("w-32")
        start_button = ui.button("Run analysis")
        cancel_button = ui.button("Cancel", on_click=task_state.request_cancel)
        cancel_button.visible = False

    def _on_run() -> None:
        kf = app_state.selected_file
        if not kf:
            ui.notify("Select a file first", color="warning")
            return
        window_value = window_input.value
        window = int(window_value)

        def _after_result(_success: bool) -> None:
            app_state.notify_metadata_changed(kf)

        run_flow_analysis(
            kf,
            task_state,
            window_size=window,
            on_result=_after_result,
        )

    start_button.on("click", _on_run)

    @task_state.events.running.connect  # type: ignore[attr-defined]
    def _toggle_buttons() -> None:
        start_button.disabled = task_state.running
        cancel_button.visible = task_state.running and task_state.cancellable
