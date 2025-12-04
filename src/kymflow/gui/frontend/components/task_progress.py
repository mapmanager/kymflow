from __future__ import annotations

from nicegui import ui

from kymflow.core.state_v2 import TaskState


def create_task_progress(task_state: TaskState) -> None:
    bar = ui.linear_progress(value=0).classes("w-full")
    status = ui.label("")

    def _on_progress(value: float) -> None:
        bar.value = value
        status.set_text(task_state.message)

    def _on_running_changed(running: bool) -> None:
        if running:
            bar.visible = True
        else:
            bar.visible = False
            bar.value = 0.0
    
    # Register callbacks (no decorators)
    task_state.on_progress_changed(_on_progress)
    task_state.on_running_changed(_on_running_changed)
