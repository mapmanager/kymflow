"""File table view component using CustomAgGrid.

This module provides a view component that displays a table of kymograph files
using CustomAgGrid. The view emits FileSelection (phase="intent") events when
users select rows, but does not subscribe to events (that's handled by FileTableBindings).
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional, TYPE_CHECKING

from kymflow.core.image_loaders.kym_image import KymImage
from nicegui import ui
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import FileSelection, MetadataUpdate, AnalysisUpdate, SelectionOrigin
from kymflow.gui_v2.events_state import TaskStateChanged
from kymflow.core.utils.logging import get_logger
from nicewidgets.custom_ag_grid.config import ColumnConfig, GridConfig, SelectionMode
from nicewidgets.custom_ag_grid.custom_ag_grid_v2 import CustomAgGrid_v2

if TYPE_CHECKING:
    from kymflow.gui_v2.app_context import AppContext

Rows = List[dict[str, object]]
OnSelected = Callable[[FileSelection], None]
OnMetadataUpdate = Callable[[MetadataUpdate], None]
OnAnalysisUpdate = Callable[[AnalysisUpdate], None]

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
    filterable: bool = False,
    editor: Optional[str] = None,
    extra_grid_options: Optional[dict[str, object]] = None,
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

    # Merge any additional grid options
    if extra_grid_options is not None:
        extra.update(extra_grid_options)

    col_config = ColumnConfig(
        field=field,
        header=header,
        editable=editable,
        filterable=filterable,
        extra_grid_options=extra,
    )
    if editor is not None:
        col_config.editor = editor  # type: ignore[assignment]
    return col_config

def _default_columns() -> list[ColumnConfig]:
    return [
        _col("File Name", "File Name", filterable=True, flex=2, width=180, min_width=180),
        _col("Analyzed", "Analyzed", width=90, cell_class="ag-cell-center", extra_grid_options={
            ":cellRenderer": "(params) => params.value === 'True' ? '✓' : ''"
        }),
        _col("Saved", "Saved", width=80, cell_class="ag-cell-center", extra_grid_options={
            ":cellRenderer": "(params) => params.value === 'False' ? '❌' : ''"
        }),
        _col("Num ROIS", "ROIS", width=100, cell_class="ag-cell-right"),
        _col("Total Num Velocity Events", "Events", width=100, cell_class="ag-cell-right"),  # abb 202601
        _col("User Event", "User Event", width=100, cell_class="ag-cell-right"),
        
        _col("Parent Folder", "Parent", flex=1, min_width=120, hide=True),
        _col("Grandparent Folder", "Grandparent", filterable=True, flex=1, min_width=120, hide=True),
        
        _col("condition", "Condition", filterable=True, flex=1, min_width=100),
        # _col("condition2", "Condition 2", filterable=True, flex=1, min_width=100),
        _col("treatment", "Treatment", filterable=True, flex=1, min_width=100),
        # _col("treatment2", "Treatment 2", filterable=True, flex=1, min_width=100),
        _col("date", "Date", filterable=True, flex=1, min_width=90),
        _col("duration (s)", "Duration (s)", width=140, cell_class="ag-cell-right"),
        _col("length (um)", "Length (um)", width=140, cell_class="ag-cell-right"),
        _col("note", "Note", flex=1, min_width=160, editable=True),
        _col("accepted", "Accepted", width=100, editable=True, cell_class="ag-cell-center", editor="checkbox"),
    ]


def get_file_table_toggleable_column_fields() -> list[str]:
    """Return column field ids that can be toggled in the file table context menu.

    Excludes the row index column (handled by the grid separately). Used by
    FileTableContextMenu for the column visibility section.

    Returns:
        List of field names from the default file table columns.
    """
    return [c.field for c in _default_columns()]


def get_file_table_initial_column_visibility() -> dict[str, bool]:
    """Return initial visibility for each toggleable column based on default config.

    Uses the same ``hide`` flag that seeds AG Grid ``columnDefs`` so the context
    menu's initial checkmarks match the configured file table column visibility.

    Returns:
        Mapping from column field name to ``True`` (visible) or ``False`` (hidden).
    """
    visibility: dict[str, bool] = {}
    for col in _default_columns():
        extra = col.extra_grid_options or {}
        hidden = bool(extra.get("hide", False))
        visibility[col.field] = not hidden
    return visibility


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
        app_context: "AppContext",
        *,
        on_selected: OnSelected,
        on_metadata_update: OnMetadataUpdate | None = None,
        on_analysis_update: OnAnalysisUpdate | None = None,
        selection_mode: SelectionMode = "single",
        on_build_context_menu: Optional[Callable[[], None]] = None,
    ) -> None:
        self._app_context = app_context
        self._on_selected = on_selected
        self._on_metadata_update = on_metadata_update
        self._on_analysis_update = on_analysis_update
        self._selection_mode = selection_mode
        self._on_build_context_menu: Optional[Callable[[], None]] = on_build_context_menu

        # Grid and context menu (builder set later via set_context_menu_builder if needed).
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

        # Create grid container with flex constraints for proper rendering at all window sizes
        # Parent container (home_page) already provides flex column context
        # Match kym_event_view structure: h-full + flex flex-col + overflow-hidden for proper sizing

        # self._grid_container = ui.column().classes("w-full h-full flex-1 min-h-0 min-w-0 flex flex-col overflow-hidden")

        # self._grid_container = ui.column().classes(
        #     "w-full h-full min-h-0 flex flex-col overflow-hidden"
        # )


        self._grid_container = ui.column().classes(
            "w-full h-full min-h-0 min-w-0 flex flex-col overflow-hidden"
        )


        # self._grid_container = ui.column().classes("w-full flex-1 min-h-0 min-w-0 flex flex-col overflow-hidden")
        self._create_grid(self._pending_rows)
        self._update_interaction_state()

    def set_context_menu_builder(self, builder: Optional[Callable[[], None]]) -> None:
        """Set the callback used to build the grid's right-click context menu.

        Must be called before the first render() so the grid receives the builder.
        If the grid was already created (e.g. after navigation), the next render()
        will use the new builder.

        Args:
            builder: Called when the user opens the context menu; it should add
                ui.menu_item(...) and ui.separator() to the current menu context.
        """
        self._on_build_context_menu = builder

    def _create_grid(self, rows: Rows) -> None:
        """Create a fresh grid instance inside the current container."""
        # if self._grid_container is None:
        #     return
        grid_cfg = GridConfig(
            selection_mode=self._selection_mode,  # type: ignore[arg-type]
            # height="24rem",
            row_id_field="path",
            show_row_index=True,
            row_index_width=60,  # Wider to fit index >= 100
            zebra_rows=False,
            hover_highlight=False,
        )

        self._grid = CustomAgGrid_v2(
            data=rows,
            columns=_default_columns(),
            grid_config=grid_cfg,
            parent=self._grid_container,
            runtimeWidgetName="FileTableView",
            on_build_context_menu=self._on_build_context_menu,
        )
        self._grid.on_row_selected(self._on_row_selected)
        self._grid.on_cell_edited(self._on_cell_edited)

    def set_files(self, files: Iterable[KymImage]) -> None:
        """Update table contents from KymImage list."""
        files_list = list(files)
        
        # logger.info(f'files_list:{len(files_list)}')

        self._files = files_list
        self._files_by_path = {
            str(f.path): f for f in files_list if getattr(f, "path", None) is not None
        }
        # Get blinded setting from AppConfig
        blinded = self._app_context.app_config.get_blinded() if self._app_context.app_config else False
        rows: Rows = [
            f.getRowDict(blinded=blinded)
            for f in files_list
        ]
        rows_unchanged = rows == self._pending_rows
        
        # logger.info(f'=== rows: {len(rows)}')
        
        # for _row in rows:
        #     logger.info(f'  {_row}')
        
        # logger.info(f'rows_unchanged:{rows_unchanged}')

        self._pending_rows = rows
        if rows_unchanged and self._grid is not None:
            # logger.debug("rows unchanged -->> skip refresh")
            return
        
        # logger.error(f'self._grid_container:{self._grid_container}')

        if self._grid is not None:
            self._grid.set_data(rows)

    def update_row_for_file(self, file: KymImage) -> None:
        """Update a single table row for the given KymImage in-place.

        This recomputes the row dict for ``file`` and, if the grid is active
        and the file is present in the current table, forwards the update to
        the underlying CustomAgGrid_v2 instance. Internal caches such as
        ``_pending_rows`` and ``_files_by_path`` are kept in sync.
        """
        if self._grid is None:
            return
        if getattr(file, "path", None) is None:
            return

        path = str(file.path)
        if path not in self._files_by_path:
            return

        # Ensure our file cache points at the latest object
        self._files_by_path[path] = file

        blinded = self._app_context.app_config.get_blinded() if self._app_context.app_config else False
        row = file.getRowDict(blinded=blinded)
        self.update_row_for_path(path, row)

    def update_row_for_path(self, path: str, row: dict[str, object]) -> None:
        """Low-level helper to update a single row by its file path."""
        if self._grid is None:
            return

        # Update pending_rows cache
        updated = False
        for i, existing in enumerate(self._pending_rows):
            if str(existing.get("path")) == str(path):
                self._pending_rows[i] = dict(row)
                updated = True
                break

        if not updated:
            # If the row is not currently present (e.g. table filtered or empty),
            # do not attempt to update the grid.
            return

        # Forward to CustomAgGrid_v2 for in-place row update
        if hasattr(self._grid, "update_row"):
            self._grid.update_row(path, row)  # type: ignore[arg-type]

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
        path = row_data.get("path")
        if not path:
            return
        file = self._files_by_path.get(str(path))
        if file is None:
            return
        
        if field == "note":
            if self._on_metadata_update is None:
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
        elif field == "accepted":
            if self._on_analysis_update is None:
                return
            # Convert new_value to bool (handle various input types)
            if isinstance(new_value, bool):
                bool_value = new_value
            elif isinstance(new_value, str):
                bool_value = new_value.lower() in ("true", "1", "yes", "on")
            else:
                bool_value = bool(new_value)
            
            self._on_analysis_update(
                AnalysisUpdate(
                    file=file,
                    fields={"accepted": bool_value},
                    origin=SelectionOrigin.FILE_TABLE,
                    phase="intent",
                )
            )

    def get_table_as_text(self) -> str:
        """Get current table data as tab-separated values (TSV) string.

        Includes all columns (ignores hide=True). Empty string if no data.

        Returns:
            TSV-formatted string with all columns and rows.
        """
        if not self._pending_rows:
            return ""

        columns = _default_columns()

        # Header row from column definitions (all columns)
        headers = [col.header or col.field for col in columns]

        rows: list[str] = []
        for row_dict in self._pending_rows:
            row_values = []
            for col in columns:
                value = row_dict.get(col.field, "")
                if value is None:
                    value_str = ""
                elif value == "":
                    value_str = ""
                else:
                    value_str = str(value)
                value_str = value_str.replace("\t", " ").replace("\n", " ").replace("\r", " ")
                row_values.append(value_str)
            rows.append("\t".join(row_values))

        return "\t".join(headers) + "\n" + "\n".join(rows)