"""File table view component using CustomAgGrid.

This module provides a view component that displays a table of kymograph files
using CustomAgGrid. The view emits FileSelection (phase="intent") events when
users select rows, but does not subscribe to events (that's handled by FileTableBindings).
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional

from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.events import FileSelection, SelectionOrigin
from nicewidgets.custom_ag_grid.config import ColumnConfig, GridConfig
from nicewidgets.custom_ag_grid.custom_ag_grid import CustomAgGrid

Rows = List[dict[str, object]]
OnSelected = Callable[[FileSelection], None]


def _col(
    field: str,
    header: Optional[str] = None,
    *,
    width: Optional[int] = None,
    hide: bool = False,
    cell_class: Optional[str] = None,
) -> ColumnConfig:
    extra: dict[str, object] = {}
    if width is not None:
        extra["width"] = width
    if hide:
        extra["hide"] = True
    if cell_class is not None:
        extra["cellClass"] = cell_class
    return ColumnConfig(field=field, header=header, extra_grid_options=extra)


def _default_columns() -> list[ColumnConfig]:
    return [
        _col("File Name", "File Name", width=260),
        _col("Analyzed", "Analyzed", width=90, cell_class="ag-cell-center"),
        _col("Saved", "Saved", width=80, cell_class="ag-cell-center"),
        _col("Num ROIS", "Num ROIS", width=100, cell_class="ag-cell-right"),
        _col("Parent Folder", "Parent Folder", width=180),
        _col("Grandparent Folder", "Grandparent Folder", width=200),
        _col("pixels", "pixels", width=110, cell_class="ag-cell-right"),
        _col("lines", "lines", width=110, cell_class="ag-cell-right"),
        _col("duration (s)", "duration (s)", width=140, cell_class="ag-cell-right"),
        _col("ms/line", "ms/line", width=120, cell_class="ag-cell-right"),
        _col("um/pixel", "um/pixel", width=120, cell_class="ag-cell-right"),
        _col("note", "note", width=240),
        _col("path", "path", hide=True),  # keep for row id + selection, but hide
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
        selection_mode: str = "single",
    ) -> None:
        self._on_selected = on_selected
        self._selection_mode = selection_mode

        self._grid: CustomAgGrid | None = None
        self._suppress_emit: bool = False

        # Keep latest rows so if FileListChanged arrives before render(),
        # we can populate when render() happens.
        self._pending_rows: Rows = []

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

        grid_cfg = GridConfig(
            selection_mode=self._selection_mode,  # type: ignore[arg-type]
            height="24rem",
        )
        if hasattr(grid_cfg, "row_id_field"):
            setattr(grid_cfg, "row_id_field", "path")

        # Create the grid *now*, inside whatever container the caller opened.
        self._grid = CustomAgGrid(
            data=self._pending_rows,
            columns=_default_columns(),
            grid_config=grid_cfg,
        )
        self._grid.on_row_selected(self._on_row_selected)

    def set_files(self, files: Iterable[KymImage]) -> None:
        """Update table contents from KymImage list."""
        rows: Rows = [f.getRowDict() for f in files]
        self._pending_rows = rows
        if self._grid is not None:
            self._grid.set_data(rows)

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