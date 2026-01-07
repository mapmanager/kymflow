# src/kymflow/gui_v2/views/file_table_view.py
# gpt 20260106: adapt to nicewidgets ColumnConfig API (no width/hide/align kwargs);
#              use extra_grid_options for AG Grid-only settings.

from __future__ import annotations

from typing import Callable

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.events import FileSelected, FilesSelected, SelectionOrigin
from nicewidgets.custom_ag_grid.config import ColumnConfig, GridConfig
from nicewidgets.custom_ag_grid.custom_ag_grid import CustomAgGrid


def _col(
    field: str,
    header: str,
    *,
    width: int | None = None,
    hide: bool = False,
    cell_class: str | None = None,
) -> ColumnConfig:
    """Helper to build ColumnConfig using extra_grid_options for AG Grid props."""
    extra: dict[str, object] = {}
    if width is not None:
        extra["width"] = width
    if hide:
        extra["hide"] = True
    if cell_class:
        extra["cellClass"] = cell_class

    return ColumnConfig(
        field=field,
        header=header,
        extra_grid_options=extra,  # gpt 20260106
    )


def _default_columns() -> list[ColumnConfig]:
    """Column setup matching KymImage.getRowDict() keys."""
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
        _col("path", "path", hide=True),  # stable row id field
    ]


class FileTableView:
    """Thin view wrapper around CustomAgGrid for KymImage rows."""

    def __init__(
        self,
        *,
        on_selected: Callable[[FileSelected | FilesSelected], None],
        selection_mode: str = "single",
    ) -> None:
        self._on_selected = on_selected

        grid_cfg = GridConfig(
            selection_mode=selection_mode,  # "single" or "multiple"
            height="28rem",
            row_id_field="path",  # stable id for programmatic selection
        )

        self._grid = CustomAgGrid(
            data=[],
            columns=_default_columns(),
            grid_config=grid_cfg,
        )

        self._grid.on_row_selected(self._handle_row_selected)

    def set_files(self, files: list[KymImage]) -> None:
        """Replace grid rows with file.getRowDict()."""
        self._grid.set_data([f.getRowDict() for f in files])

    def set_selected_paths(self, paths: list[str], *, origin: SelectionOrigin) -> None:
        """Programmatically select one or more rows by path."""
        self._grid.set_selected_row_ids(paths, origin=origin.value)

    def _handle_row_selected(self, row_index: int, row_data: dict) -> None:
        """Receive selection from grid and emit typed selection event."""
        path = row_data.get("path")
        if self._grid_config_selection_mode() == "multiple":
            # For now, CustomAgGrid v1 API gives single row events; we emit a single-item list.
            self._on_selected(
                FilesSelected(paths=[path] if path else [], origin=SelectionOrigin.FILE_TABLE)
            )
        else:
            self._on_selected(
                FileSelected(path=str(path) if path else None, origin=SelectionOrigin.FILE_TABLE)
            )

    def _grid_config_selection_mode(self) -> str:
        # gpt 20260106: CustomAgGrid doesn't expose selection_mode property in your original file;
        # we read from the grid options as a safe fallback.
        return self._grid.grid.options.get("rowSelection") or "single"