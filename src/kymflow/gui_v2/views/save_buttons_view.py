"""Save buttons view component.

This module provides a view component that displays save buttons (Save Selected
and Save All). The view emits SaveSelected(phase="intent") and SaveAll(phase="intent")
events when users click buttons, but does not subscribe to events (that's handled
by SaveButtonsBindings).
"""

from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import SaveAll, SaveSelected
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

OnSaveSelected = Callable[[SaveSelected], None]
OnSaveAll = Callable[[SaveAll], None]


class SaveButtonsView:
    """Save buttons view component.

    This view displays Save Selected and Save All buttons. Users can click these
    buttons to save analysis results, which triggers SaveSelected or SaveAll
    intent events.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by bindings)
        - Events emitted via callbacks

    Attributes:
        _on_save_selected: Callback function that receives SaveSelected events.
        _on_save_all: Callback function that receives SaveAll events.
        _save_selected_button: Save Selected button (created in render()).
        _save_all_button: Save All button (created in render()).
        _current_file: Currently selected file (for enabling/disabling Save Selected).
        _task_state: Current task state (for button states).
    """

    def __init__(
        self,
        *,
        on_save_selected: OnSaveSelected,
        on_save_all: OnSaveAll,
    ) -> None:
        """Initialize save buttons view.

        Args:
            on_save_selected: Callback function that receives SaveSelected events.
            on_save_all: Callback function that receives SaveAll events.
        """
        self._on_save_selected = on_save_selected
        self._on_save_all = on_save_all

        # UI components (created in render())
        self._save_selected_button: Optional[ui.button] = None
        self._save_all_button: Optional[ui.button] = None

        # State
        self._current_file: Optional[KymImage] = None
        self._task_state: Optional[TaskStateChanged] = None

    def render(self) -> None:
        """Create the save buttons UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.
        """
        # Always reset UI element references
        self._save_selected_button = None
        self._save_all_button = None

        with ui.row().classes("gap-2 items-start"):
            self._save_selected_button = ui.button(
                "Save Selected",
                on_click=self._on_save_selected_click, icon="save"
            ).props('dense').classes('text-sm')
            self._save_all_button = ui.button(
                "Save All",
                on_click=self._on_save_all_click
            ).props('dense').classes('text-sm')

        # Initialize button states
        self._update_button_states()

    def set_selected_file(self, file: Optional[KymImage]) -> None:
        """Update view for new file selection.

        Called by bindings when FileSelection(phase="state") event is received.
        Enables/disables Save Selected button based on file selection.

        Args:
            file: Selected KymImage instance, or None if selection cleared.
        """
        safe_call(self._set_selected_file_impl, file)

    def _set_selected_file_impl(self, file: Optional[KymImage]) -> None:
        """Internal implementation of set_selected_file."""
        self._current_file = file
        self._update_button_states()

    def set_task_state(self, task_state: TaskStateChanged) -> None:
        """Update view for task state changes.

        Called by bindings when TaskStateChanged event is received.
        Updates button states based on task running state.

        Args:
            task_state: Current task state.
        """
        safe_call(self._set_task_state_impl, task_state)

    def _set_task_state_impl(self, task_state: TaskStateChanged) -> None:
        """Internal implementation of set_task_state."""
        self._task_state = task_state
        self._update_button_states()

    def _update_button_states(self) -> None:
        """Update button states based on current file and task state."""
        if self._save_selected_button is None or self._save_all_button is None:
            return

        running = self._task_state.running if self._task_state else False

        # Disable buttons when task is running
        if running:
            self._save_selected_button.disable()
            self._save_all_button.disable()
        else:
            # Save Selected: enabled when file is selected (and not running)
            has_file = self._current_file is not None
            if has_file:
                self._save_selected_button.enable()
            else:
                self._save_selected_button.disable()

            # Save All: always enabled when not running (will check files in controller)
            self._save_all_button.enable()

    def _on_save_selected_click(self) -> None:
        """Handle Save Selected button click."""
        # Emit intent event
        self._on_save_selected(
            SaveSelected(
                phase="intent",
            )
        )

    def _on_save_all_click(self) -> None:
        """Handle Save All button click."""
        # Emit intent event
        self._on_save_all(
            SaveAll(
                phase="intent",
            )
        )
