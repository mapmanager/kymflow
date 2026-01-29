"""Bindings between FolderSelectorView and task state updates."""

from __future__ import annotations

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events_state import FileListChanged, TaskStateChanged
from kymflow.gui_v2.views.folder_selector_view import FolderSelectorView


class FolderSelectorBindings:
    """Bind FolderSelectorView to task state updates for enable/disable."""

    def __init__(self, bus: EventBus, view: FolderSelectorView) -> None:
        self._bus: EventBus = bus
        self._view: FolderSelectorView = view
        self._subscribed: bool = False

        bus.subscribe(FileListChanged, self._on_file_list_changed)
        bus.subscribe_state(TaskStateChanged, self._on_task_state_changed)
        self._subscribed = True

    def teardown(self) -> None:
        """Unsubscribe from all events (cleanup)."""
        if not self._subscribed:
            return
        self._bus.unsubscribe(FileListChanged, self._on_file_list_changed)
        self._bus.unsubscribe_state(TaskStateChanged, self._on_task_state_changed)
        self._subscribed = False

    def _on_file_list_changed(self, e: FileListChanged) -> None:
        """Handle file list changes by updating the folder display."""
        safe_call(self._view.set_folder_from_state)

    def _on_task_state_changed(self, e: TaskStateChanged) -> None:
        """Handle task state changes by disabling/enabling controls."""
        if e.task_type == "home":
            safe_call(self._view.set_task_state, e)
