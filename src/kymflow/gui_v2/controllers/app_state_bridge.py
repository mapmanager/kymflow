"""Bridge between AppState callbacks and EventBus.

This module provides a controller that connects the legacy AppState callback
system to the new v2 EventBus, allowing v2 components to react to AppState
changes while maintaining AppState as the single source of truth.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_state import FileListChanged, SelectedFileChanged

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage
    from kymflow.gui.events import SelectionOrigin


class AppStateBridgeController:
    """Bridge AppState callbacks into the v2 EventBus.

    This controller subscribes to AppState callback registries and emits
    corresponding events on the EventBus. This allows v2 components (views,
    bindings) to react to AppState changes via the event bus, while keeping
    AppState as the single source of truth.

    Flow:
        AppState.load_folder() → callback → emit FileListChanged
        AppState.select_file() → callback → emit SelectedFileChanged

    Attributes:
        _app_state: AppState instance (shared, process-level).
        _bus: EventBus instance (per-client).
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize the bridge controller.

        Subscribes to AppState callbacks. The callbacks remain registered
        for the lifetime of the AppState instance (which is a process-level
        singleton), so this bridge effectively lives for the app lifetime.

        Args:
            app_state: Shared AppState instance.
            bus: Per-client EventBus instance.
        """
        self._app_state: AppState = app_state
        self._bus: EventBus = bus

        # Register callbacks that will emit bus events
        self._app_state.on_file_list_changed(self._on_file_list_changed)
        self._app_state.on_selection_changed(self._on_selection_changed)

    def _on_file_list_changed(self) -> None:
        """Handle AppState file list change callback.

        Emits FileListChanged event with the current file list from AppState.
        """
        self._bus.emit(FileListChanged(files=list(self._app_state.files)))

    def _on_selection_changed(
        self, kym_file: KymImage | None, origin: SelectionOrigin | None
    ) -> None:
        """Handle AppState selection change callback.

        Emits SelectedFileChanged event with the current selection and origin.
        The origin is preserved through AppState so bindings can prevent
        feedback loops.

        Args:
            kym_file: Selected KymImage instance, or None if nothing selected.
            origin: SelectionOrigin indicating where the selection came from.
        """
        self._bus.emit(SelectedFileChanged(file=kym_file, origin=origin))
