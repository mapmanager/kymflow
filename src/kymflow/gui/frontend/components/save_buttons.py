from __future__ import annotations

from nicegui import ui

from kymflow.kymflow_core.state import AppState, TaskState


def create_save_buttons(app_state: AppState, task_state: TaskState) -> None:
    """Create Save Selected and Save All buttons."""

    def _save_selected() -> None:
        """Save the currently selected file if it has analysis."""
        kf = app_state.selected_file
        if not kf:
            ui.notify("No file selected", color="warning")
            return

        if not kf.analysisExists:
            ui.notify(f"No analysis found for {kf.path.name}", color="warning")
            return

        try:
            success = kf.save_analysis()
            if success:
                ui.notify(f"Saved {kf.path.name}", color="positive")
                app_state.refresh_file_rows()
            else:
                ui.notify(f"Nothing to save for {kf.path.name}", color="info")
        except Exception as e:
            ui.notify(f"Error saving {kf.path.name}: {str(e)}", color="negative")

    def _save_all() -> None:
        """Save all files that have analysis."""
        if not app_state.files:
            ui.notify("No files loaded", color="warning")
            return

        saved_count = 0
        skipped_count = 0
        error_count = 0

        for kf in app_state.files:
            if not kf.analysisExists:
                skipped_count += 1
                continue

            try:
                success = kf.save_analysis()
                if success:
                    saved_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                error_count += 1
                ui.notify(f"Error saving {kf.path.name}: {str(e)}", color="negative")

        if saved_count > 0:
            ui.notify(f"Saved {saved_count} file(s)", color="positive")
            app_state.refresh_file_rows()
        if skipped_count > 0 and saved_count == 0:
            ui.notify(
                f"Skipped {skipped_count} file(s) (no changes or no analysis)",
                color="info",
            )
        if error_count > 0:
            ui.notify(f"Errors saving {error_count} file(s)", color="negative")

    with ui.row().classes("gap-2 items-center"):
        save_selected_button = ui.button(
            "Save Selected", on_click=_save_selected, icon="save"
        )
        save_all_button = ui.button("Save All", on_click=_save_all, icon="save_alt")

    # Sync buttons based on task state; keep it on the UI thread via timer polling
    def _sync_buttons() -> None:
        running = task_state.running
        if running:
            save_selected_button.disable()
            save_all_button.disable()
            save_selected_button.props("color=red")
            save_all_button.props("color=red")
        else:
            save_selected_button.enable()
            save_all_button.enable()
            save_selected_button.props(remove="color")
            save_all_button.props(remove="color")

    _sync_buttons()
    ui.timer(0.2, _sync_buttons)
