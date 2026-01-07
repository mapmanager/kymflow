# src/kymflow/gui_v2/controllers/app_state_bridge.py
from __future__ import annotations

from kymflow.gui.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_state import FileListChanged, SelectedFileChanged


class AppStateBridgeController:
    """Bridge AppState callbacks into the v2 EventBus.

    This lets you keep AppState as the source of truth while still getting a clean
    bus trace for signal flow.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        self._app_state = app_state
        self._bus = bus

        self._app_state.on_file_list_changed(self._on_file_list_changed)
        self._app_state.on_selection_changed(self._on_selection_changed)

    def _on_file_list_changed(self) -> None:
        self._bus.emit(FileListChanged(files=list(self._app_state.files)))

    def _on_selection_changed(self, kym_file, origin) -> None:
        self._bus.emit(SelectedFileChanged(file=kym_file, origin=origin))
