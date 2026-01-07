# src/kymflow/gui_v2/views/file_table_bindings.py
from __future__ import annotations

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import SelectionOrigin
from kymflow.gui_v2.events_state import FileListChanged, SelectedFileChanged
from kymflow.gui_v2.views.file_table_view import FileTableView


class FileTableBindings:
    """Bind FileTableView to bus events (state -> view updates)."""

    def __init__(self, bus: EventBus, table: FileTableView) -> None:
        self._table = table
        bus.subscribe(FileListChanged, self._on_file_list_changed)
        bus.subscribe(SelectedFileChanged, self._on_selected_file_changed)

    def _on_file_list_changed(self, e: FileListChanged) -> None:
        self._table.set_files(e.files)

    def _on_selected_file_changed(self, e: SelectedFileChanged) -> None:
        if e.file is None:
            self._table.set_selected_paths([], origin=SelectionOrigin.EXTERNAL)
        else:
            self._table.set_selected_paths([str(e.file.path)], origin=SelectionOrigin.EXTERNAL)
