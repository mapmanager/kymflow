"""Task progress view component.

This module provides a view component that displays task progress (progress bar
and status message). The view does not emit events, only displays state.
"""

from __future__ import annotations

from typing import Optional

from nicegui import ui

from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


class TaskProgressView:
    """Task progress view component.

    This view displays a progress bar and status message for long-running tasks.
    It updates based on TaskStateChanged events received via bindings.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by bindings)

    Attributes:
        _progress_bar: Progress bar UI element (created in render()).
        _status_label: Status message label (created in render()).
        _task_state: Current task state.
    """

    def __init__(self) -> None:
        """Initialize task progress view."""
        # UI components (created in render())
        self._progress_bar: Optional[ui.linear_progress] = None
        self._status_label: Optional[ui.label] = None

        # State
        self._task_state: Optional[TaskStateChanged] = None

    def render(self) -> None:
        """Create the task progress UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.
        """
        # Always reset UI element references
        self._progress_bar = None
        self._status_label = None

        self._progress_bar = ui.linear_progress(value=0).classes("w-full")
        self._status_label = ui.label("")

        # Initialize state
        if self._task_state is not None:
            self._update_display()

    def set_task_state(self, task_state: TaskStateChanged) -> None:
        """Update view for task state changes.

        Called by bindings when TaskStateChanged event is received.
        Updates progress bar and status message.

        Args:
            task_state: Current task state.
        """
        safe_call(self._set_task_state_impl, task_state)

    def _set_task_state_impl(self, task_state: TaskStateChanged) -> None:
        """Internal implementation of set_task_state."""
        self._task_state = task_state
        self._update_display()

    def _update_display(self) -> None:
        """Update progress bar and status label from current task state."""
        if self._progress_bar is None or self._status_label is None:
            return

        if self._task_state is None:
            self._progress_bar.value = 0.0
            self._status_label.text = ""
            self._progress_bar.visible = False
            return

        # Update progress bar
        self._progress_bar.value = self._task_state.progress
        self._status_label.text = self._task_state.message

        # Show/hide progress bar based on running state
        # Also show if there's a message (even if not running, to show final status)
        if self._task_state.running or (self._task_state.message and self._task_state.progress > 0):
            self._progress_bar.visible = True
        else:
            self._progress_bar.visible = False
            if not self._task_state.running:
                self._progress_bar.value = 0.0
