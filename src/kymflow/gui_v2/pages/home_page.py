"""Home page for GUI v2 with folder selection and file table."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.gui.app_context import AppContext
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.app_state_bridge import AppStateBridgeController
from kymflow.gui_v2.controllers.file_selection_controller import FileSelectionController
from kymflow.gui_v2.controllers.file_table_persistence import FileTablePersistenceController
from kymflow.gui_v2.controllers.folder_controller import FolderController
from kymflow.gui_v2.events import SelectionOrigin
from kymflow.gui_v2.pages.base_page import BasePage
from kymflow.gui_v2.views.file_table_bindings import FileTableBindings
from kymflow.gui_v2.views.file_table_view import FileTableView
from kymflow.gui_v2.views.folder_selector_view import FolderSelectorView

if TYPE_CHECKING:
    pass


class HomePage(BasePage):
    """Home page: folder selector + file table wired through the event bus.

    This page provides the main file browsing and selection interface:
    - Folder selection and reload
    - File table with single selection
    - Automatic selection persistence across page reloads

    Lifecycle:
        - Controllers and bindings are created once per client in _ensure_setup()
        - UI elements are created fresh on each render() in build()
        - Selection is restored once per client session after UI is created

    Attributes:
        _bridge: Bridges AppState callbacks to event bus.
        _folder_controller: Handles folder selection events.
        _file_selection_controller: Handles file selection events.
        _persistence: Persists file selection to browser storage.
        _folder_view: Folder selector UI component.
        _table_view: File table UI component (CustomAgGrid).
        _table_bindings: Binds table view to event bus (state → view updates).
        _restored_once: Tracks if selection has been restored for this client.
    """

    def __init__(self, context: AppContext, bus: EventBus) -> None:
        """Initialize HomePage.

        Args:
            context: Shared application context.
            bus: Per-client EventBus instance.
        """
        super().__init__(context, bus)

        # Controllers and bindings will be created in _ensure_setup() (once per client)
        self._bridge: AppStateBridgeController | None = None
        self._folder_controller: FolderController | None = None
        self._file_selection_controller: FileSelectionController | None = None
        self._persistence: FileTablePersistenceController | None = None

        # View objects (created in __init__, UI elements created in build())
        self._folder_view = FolderSelectorView(bus, context.app_state)
        self._table_view = FileTableView(on_selected=bus.emit, selection_mode="single")
        self._table_bindings: FileTableBindings | None = None

        # Per-client state tracking
        self._restored_once: bool = False
        self._setup_complete: bool = False

    def _ensure_setup(self) -> None:
        """Ensure controllers and bindings are set up once per client.

        This method is idempotent and will only create controllers/bindings
        once per client session, preventing duplicate event subscriptions.
        """
        if self._setup_complete:
            return

        # Controllers (subscribe to events once per client)
        self._bridge = AppStateBridgeController(self.context.app_state, self.bus)
        self._folder_controller = FolderController(self.context.app_state, self.bus)
        self._file_selection_controller = FileSelectionController(
            self.context.app_state, self.bus
        )

        self._persistence = FileTablePersistenceController(
            self.context.app_state,
            self.bus,
            storage_key="kymflow_selected_file_path_v2",
        )

        # Bindings (subscribe to events once per client)
        self._table_bindings = FileTableBindings(self.bus, self._table_view)

        self._setup_complete = True

    def build(self) -> None:
        """Build the Home page UI.

        Creates the folder selector and file table UI elements. This method
        is called every time the page is rendered, but controllers/bindings
        are only created once per client (in _ensure_setup()).

        Selection restoration happens after the UI is created, but only once
        per client session to avoid overwriting user selections.
        """
        with ui.column().classes("w-full p-4 gap-4"):
            # Folder selector FIRST (renders first in DOM)
            initial_folder = self.context.app_state.folder or Path(".")
            self._folder_view.render(initial_folder=initial_folder)

            # File table SECOND (creates grid ui here)
            self._table_view.render()

            # Populate with current state (if already loaded, shows immediately)
            self._table_view.set_files(list(self.context.app_state.files))

            # Restore selection once per client (after UI is created)
            if not self._restored_once:
                if self._persistence is not None:
                    restored = self._persistence.restore_selection()
                    if restored:
                        self._table_view.set_selected_paths(
                            restored, origin=SelectionOrigin.RESTORE
                        )
                self._restored_once = True