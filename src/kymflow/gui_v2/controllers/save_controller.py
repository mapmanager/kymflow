"""Controller for handling save events from the UI.

This module provides a controller that translates user save intents
(SaveSelected and SaveAll phase="intent") into file save operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.core.state import TaskState
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import SaveAll, SaveSelected
from kymflow.core.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class SaveController:
    """Apply save intent events to file save operations.

    This controller handles save intent events from the UI (typically
    from the save buttons) and saves analysis results to files.

    Update Flow:
        1. User clicks "Save Selected" → SaveButtonsView emits SaveSelected(phase="intent")
        2. This controller receives event → checks file has analysis → calls save_analysis()
        3. User clicks "Save All" → SaveButtonsView emits SaveAll(phase="intent")
        4. This controller receives event → iterates files → saves those with analysis

    Attributes:
        _app_state: AppState instance to access files.
        _task_state: TaskState instance (for checking if task is running).
    """

    def __init__(self, app_state: AppState, task_state: TaskState, bus: EventBus) -> None:
        """Initialize save controller.

        Subscribes to SaveSelected and SaveAll (phase="intent") events from the bus.

        Args:
            app_state: AppState instance to access files.
            task_state: TaskState instance (for checking if task is running).
            bus: EventBus instance to subscribe to.
        """
        self._app_state: AppState = app_state
        self._task_state: TaskState = task_state
        bus.subscribe_intent(SaveSelected, self._on_save_selected)
        bus.subscribe_intent(SaveAll, self._on_save_all)

    def _on_save_selected(self, e: SaveSelected) -> None:
        """Handle save selected intent event.

        Saves the currently selected file if it has analysis. Shows a notification
        if no file is selected or no analysis is found.

        Args:
            e: SaveSelected event (phase="intent").
        """
        kf = self._app_state.selected_file
        if not kf:
            ui.notify("No file selected", color="warning")
            return

        kym_analysis = kf.get_kym_analysis()
        if not kym_analysis.is_dirty:
            ui.notify(f"Nothing to save for {kf.path.name}", color="info")
            return

        try:
            success = kym_analysis.save_analysis()
            if success:
                ui.notify(f"Saved {kf.path.name}", color="positive")
                self._app_state.refresh_file_rows()
            else:
                ui.notify(f"Nothing to save for {kf.path.name}", color="info")
        except Exception as exc:
            logger.exception(f"Error saving {kf.path.name}")
            ui.notify(f"Error saving {kf.path.name}: {str(exc)}", color="negative")

    def _on_save_all(self, e: SaveAll) -> None:
        """Handle save all intent event.

        Saves all files that have analysis. Shows notifications for results.

        Args:
            e: SaveAll event (phase="intent").
        """
        if not self._app_state.files:
            ui.notify("No files loaded", color="warning")
            return

        saved_count = 0
        skipped_count = 0
        error_count = 0

        for kf in self._app_state.files:
            kym_analysis = kf.get_kym_analysis()
            if not kym_analysis.is_dirty:
                skipped_count += 1
                continue

            try:
                success = kym_analysis.save_analysis()
                if success:
                    saved_count += 1
                else:
                    skipped_count += 1
            except Exception as exc:
                logger.exception(f"Error saving {kf.path.name}")
                error_count += 1
                ui.notify(f"Error saving {kf.path.name}: {str(exc)}", color="negative")

        if saved_count > 0:
            ui.notify(f"Saved {saved_count} file(s)", color="positive")
            self._app_state.refresh_file_rows()
        if skipped_count > 0 and saved_count == 0:
            ui.notify(
                f"Skipped {skipped_count} file(s) (no changes or no analysis)",
                color="info",
            )
        if error_count > 0:
            ui.notify(f"Errors saving {error_count} file(s)", color="negative")
