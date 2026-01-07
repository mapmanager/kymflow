# src/kymflow/gui_v2/pages/home_page.py
from __future__ import annotations

from pathlib import Path

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


class HomePage(BasePage):
    """v2 Home page: folder selector + file table wired through the bus."""

    def __init__(self, context: AppContext, bus: EventBus) -> None:
        super().__init__(context, bus)

        # Controllers
        self._bridge = AppStateBridgeController(context.app_state, bus)
        self._folder_controller = FolderController(context.app_state, bus)
        self._file_selection_controller = FileSelectionController(context.app_state, bus)
        self._persistence = FileTablePersistenceController(
            context.app_state,
            bus,
            storage_key="kymflow_selected_file_path_v2",
        )

    def build(self) -> None:
        ui.label("KymFlow (v2)").classes("text-xl font-semibold")

        initial_folder = self.context.app_state.folder or Path(".")
        FolderSelectorView(self.bus, self.context.app_state).render(initial_folder=initial_folder)

        table = FileTableView(on_selected=self.bus.emit, selection_mode="single")
        FileTableBindings(self.bus, table)

        # Initial population from current AppState
        table.set_files(list(self.context.app_state.files))

        # Restore selection without feedback loops
        restored = self._persistence.restore_selection()
        if restored:
            table.set_selected_paths(restored, origin=SelectionOrigin.RESTORE)
