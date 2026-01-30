"""File table view component using CustomAgGrid.

This module provides a view component that displays a table of kymograph files
using CustomAgGrid. The view emits FileSelection (phase="intent") events when
users select rows, but does not subscribe to events (that's handled by FileTableBindings).
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional

from kymflow.core.image_loaders.kym_image import KymImage
from nicegui import ui
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import FileSelection, MetadataUpdate, SelectionOrigin
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.core.utils.logging import get_logger
from nicewidgets.custom_ag_grid.config import ColumnConfig, GridConfig, SelectionMode
# from nicewidgets.custom_ag_grid.custom_ag_grid import CustomAgGrid
from nicewidgets.custom_ag_grid.custom_ag_grid_v2 import CustomAgGrid_v2

Rows = List[dict[str, object]]
OnSelected = Callable[[FileSelection], None]
OnMetadataUpdate = Callable[[MetadataUpdate], None]

logger = get_logger(__name__)

def _col(
    field: str,
    header: Optional[str] = None,
    *,
    width: Optional[int] = None,
    min_width: Optional[int] = None,
    flex: Optional[int] = None,
    hide: bool = False,
    cell_class: Optional[str] = None,
    editable: bool = False,
) -> ColumnConfig:
    extra: dict[str, object] = {}

    # Prefer responsive sizing: flex + minWidth.
    # Only set fixed width if you really want it.
    if width is not None:
        extra["width"] = width
    if min_width is not None:
        extra["minWidth"] = min_width
    if flex is not None:
        extra["flex"] = flex

    if hide:
        extra["hide"] = True
    if cell_class is not None:
        extra["cellClass"] = cell_class

    return ColumnConfig(
        field=field,
        header=header,
        editable=editable,
        extra_grid_options=extra,
    )

def _default_columns() -> list[ColumnConfig]:
    return [
        _col("File Name", "File Name", flex=2, min_width=200),
        _col("Analyzed", "Analyzed", width=90, cell_class="ag-cell-center"),
        _col("Saved", "Saved", width=80, cell_class="ag-cell-center"),
        _col("Num ROIS", "ROIS", width=100, cell_class="ag-cell-right"),
        _col("Total Num Velocity Events", "Events", width=100, cell_class="ag-cell-right"),  # abb 202601
        _col("Parent Folder", "Parent", flex=1, min_width=120),
        _col("Grandparent Folder", "Grandparent", flex=1, min_width=120),
        _col("duration (s)", "Duration (s)", width=140, cell_class="ag-cell-right"),
        _col("length (um)", "Length (um)", width=140, cell_class="ag-cell-right"),
        _col("note", "Note", flex=1, min_width=160, editable=True),
    ]

class FileTableView:
    """File table view component using CustomAgGrid.

    This view displays a table of kymograph files with columns for file name,
    analysis status, metadata, etc. Users can select rows, which triggers
    FileSelection (phase="intent") events.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via set_files() and set_selected_paths()
        - Events emitted via on_selected callback

    Attributes:
        _on_selected: Callback function that receives FileSelection events (phase="intent").
        _selection_mode: Selection mode ("single" or "multiple").
        _grid: CustomAgGrid instance (created in render()).
        _suppress_emit: Flag to prevent event emission during programmatic selection.
        _pending_rows: Rows buffered before render() is called.
    """

    def __init__(
        self,
        *,
        on_selected: OnSelected,
        on_metadata_update: OnMetadataUpdate | None = None,
        selection_mode: SelectionMode = "single",
    ) -> None:
        self._on_selected = on_selected
        self._on_metadata_update = on_metadata_update
        self._selection_mode = selection_mode

        # self._grid: CustomAgGrid | None = None
        self._grid: CustomAgGrid_v2 | None = None
        self._grid_container: Optional[ui.element] = None  # pyinstaller table view
        self._suppress_emit: bool = False
        self._task_state: Optional[TaskStateChanged] = None

        # Keep latest rows so if FileListChanged arrives before render(),
        # we can populate when render() happens.
        self._pending_rows: Rows = []
        self._files: list[KymImage] = []
        self._files_by_path: dict[str, KymImage] = {}

    def render(self) -> None:
        """Create the grid UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.

        This method is called on every page navigation. We always recreate UI
        elements rather than trying to detect if they're still valid, which is
        simpler and more reliable.
        """
        # Always reset grid reference - NiceGUI will clean up old elements
        # This ensures we create fresh elements in the new container context
        self._grid = None
        self._grid_container = None

        grid_cfg = GridConfig(
            selection_mode=self._selection_mode,  # type: ignore[arg-type]
            # height="24rem",
            row_id_field="path",
            show_row_index=True,
            zebra_rows=False,
            hover_highlight=False,
        )
        # if hasattr(grid_cfg, "row_id_field"):
        #     setattr(grid_cfg, "row_id_field", "path")

        # Create the grid *now*, inside whatever container the caller opened.
        # self._grid_container = ui.column().classes("w-full h-full")  # pyinstaller table view
        # self._grid_container = ui.column().classes("w-full")  # pyinstaller table view
        # self._grid_container = ui.column().classes("w-full h-full min-w-0 overflow-x-auto")
        # self._grid_container = ui.column().classes("w-full h-full")
        # abb 20260129 trying to fix custom table so it is top aligned
        self._grid_container = ui.column().classes(
            "w-full h-full min-h-0 min-w-0 overflow-hidden flex flex-col"
        )
        self._create_grid(self._pending_rows, grid_cfg)
        self._update_interaction_state()

    def _create_grid(self, rows: Rows, grid_cfg: GridConfig) -> None:
        """Create a fresh grid instance inside the current container."""
        if self._grid_container is None:
            return
        self._grid = CustomAgGrid_v2(
            data=rows,
            columns=_default_columns(),
            grid_config=grid_cfg,
            parent=self._grid_container,
            runtimeWidgetName="FileTableView",
        )
        self._grid.on_row_selected(self._on_row_selected)
        self._grid.on_cell_edited(self._on_cell_edited)

    def set_files(self, files: Iterable[KymImage]) -> None:
        """Update table contents from KymImage list."""
        files_list = list(files)
        self._files = files_list
        self._files_by_path = {
            str(f.path): f for f in files_list if getattr(f, "path", None) is not None
        }
        rows: Rows = [f.getRowDict() for f in files_list]
        rows_unchanged = rows == self._pending_rows
        self._pending_rows = rows
        if rows_unchanged and self._grid is not None:
            logger.debug("FileTableView.set_files: rows unchanged; skip refresh")
            return
        if self._grid is not None:
            self._grid.set_data(rows)

    def refresh_rows(self) -> None:
        """Refresh table rows from cached files (used after metadata updates).
        
        Note: This method calls set_files() which calls _grid.set_data(), which
        clears the selection. The caller should restore the selection after calling
        this method.
        """
        if not self._files:
            return
        self.set_files(self._files)

    def set_selected_paths(self, paths: list[str], *, origin: SelectionOrigin) -> None:
        """Programmatically select rows by file path."""
        if self._grid is None:
            return
        self._suppress_emit = True
        try:
            if hasattr(self._grid, "set_selected_row_ids"):
                self._grid.set_selected_row_ids(paths, origin=origin.value)
        finally:
            self._suppress_emit = False

    def set_task_state(self, task_state: TaskStateChanged) -> None:
        """Update view for task state changes."""
        safe_call(self._set_task_state_impl, task_state)

    def _set_task_state_impl(self, task_state: TaskStateChanged) -> None:
        """Internal implementation of set_task_state."""
        self._task_state = task_state
        self._update_interaction_state()

    def _update_interaction_state(self) -> None:
        """Enable/disable user interaction based on task running state."""
        if self._grid_container is None:
            return
        running = self._task_state.running if self._task_state else False
        if running:
            self._grid_container.classes(add="pointer-events-none opacity-60")
        else:
            self._grid_container.classes(remove="pointer-events-none opacity-60")

    def _on_row_selected(self, row_index: int, row_data: dict[str, object]) -> None:
        """Handle user selecting a row."""
        if self._suppress_emit:
            return
        path = row_data.get("path")
        self._on_selected(
            FileSelection(
                path=str(path) if path else None,
                file=None,  # Intent phase - file will be looked up by controller
                origin=SelectionOrigin.FILE_TABLE,
                phase="intent",
            )
        )

    def _on_cell_edited(
        self,
        row_index: int,
        field: str,
        old_value: object,
        new_value: object,
        row_data: dict[str, object],
    ) -> None:
        """Handle user editing a cell."""
        if self._on_metadata_update is None:
            return
        if field != "note":
            return
        path = row_data.get("path")
        if not path:
            return
        file = self._files_by_path.get(str(path))
        if file is None:
            return
        if new_value is None:
            note_value = ""
        else:
            note_value = str(new_value)
            if note_value.strip() == "-" and (old_value in (None, "", "-")):
                note_value = ""
        self._on_metadata_update(
            MetadataUpdate(
                file=file,
                metadata_type="experimental",
                fields={"note": note_value},
                origin=SelectionOrigin.FILE_TABLE,
                phase="intent",
            )
        )