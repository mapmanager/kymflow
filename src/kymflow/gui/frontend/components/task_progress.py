from __future__ import annotations

from nicegui import ui

from kymflow.kymflow_core.state import TaskState


def create_task_progress(task_state: TaskState) -> None:
    bar = ui.linear_progress(value=0).classes("w-full")
    status = ui.label("")

    @task_state.progress_changed.connect
    def _on_progress(value: float) -> None:
        bar.value = value
        status.set_text(task_state.message)

    @task_state.events.running.connect  # type: ignore[attr-defined]
    def _on_running_changed() -> None:
        if task_state.running:
            bar.visible = True
        else:
            bar.visible = False
            bar.value = 0.0
