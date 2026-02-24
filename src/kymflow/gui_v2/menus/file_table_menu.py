"""File table right-click context menu: config-driven items and column visibility.

This module provides a reusable context menu for the file table grid. The menu
is rebuilt on each open (via CustomAgGrid_v2's on_build_context_menu), so content
can be dynamic (e.g. column visibility state).

Usage:
    menu = FileTableContextMenu(
        get_selected_file=lambda: app_state.selected_file,
        get_table_text=lambda: file_table_view.get_table_as_text(),
        get_grid=lambda: file_table_view._grid,
        toggleable_columns=get_file_table_toggleable_column_fields(),
        get_radon_report_text=lambda: ...,  # optional
        get_kym_event_report_text=lambda: ...,  # optional
    )
    file_table_view.set_context_menu_builder(menu.build)
"""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from nicewidgets.utils.clipboard import copy_to_clipboard
from nicewidgets.utils.file_manager import reveal_in_file_manager

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

# Checkmark prefix for visible columns in the column-visibility section.
_COLUMN_VISIBLE_PREFIX = "✓ "


# Top-level menu items (action id and display label). Order is preserved.
FILE_TABLE_CONTEXT_MENU_ITEMS = [
    {"id": "reveal_in_finder", "label": "Reveal In Finder"},
    {"id": "copy_file_table", "label": "Copy File Table"},
    {"id": "copy_radon_report", "label": "Copy Radon Report"},
    {"id": "copy_kym_event_report", "label": "Copy Kym Event Report"},
]


class FileTableContextMenu:
    """Builds the file table right-click context menu (top-level actions + column visibility).

    The menu is populated when build() is called; that call runs inside the grid's
    context menu clear-and-rebuild context (CustomAgGrid_v2), so ui.menu_item()
    and ui.separator() add to the correct menu.

    Column visibility is kept in a local cache and applied to the grid via
    setColumnsVisible. We do not read visibility from the grid on each open to
    avoid async calls; the cache is updated on each toggle and on Show all / Hide all.
    """

    def __init__(
        self,
        get_selected_file: Callable[[], Any],
        get_table_text: Callable[[], str],
        get_grid: Callable[[], Any],
        toggleable_columns: list[str],
        initial_visibility: dict[str, bool] | None = None,
        get_radon_report_text: Callable[[], str] | None = None,
        get_kym_event_report_text: Callable[[], str] | None = None,
    ) -> None:
        """Create a file table context menu builder.

        Args:
            get_selected_file: Callable that returns the currently selected file
                (object with .path) or None. Used for Reveal In Finder.
            get_table_text: Callable that returns the file table as text (e.g. TSV).
                Used for Copy File Table.
            get_grid: Callable that returns the CustomAgGrid_v2 grid instance (or None
                if the grid is not yet created). Used for column visibility toggles.
            toggleable_columns: List of column field ids that can be shown/hidden.
                Typically from get_file_table_toggleable_column_fields().
            initial_visibility: Optional mapping from column field name to initial
                visibility (True for visible, False for hidden). When provided, the
                internal visibility cache is seeded from this config-only state.
            get_radon_report_text: Optional callable that returns radon report as CSV text.
                Used for Copy Radon Report. If None, that action logs "not available".
            get_kym_event_report_text: Optional callable that returns kym event report as CSV text.
                Used for Copy Kym Event Report. If None, that action logs "not available".
        """
        self._get_selected_file = get_selected_file
        self._get_table_text = get_table_text
        self._get_grid = get_grid
        self._toggleable_columns = list(toggleable_columns)
        self._get_radon_report_text = get_radon_report_text
        self._get_kym_event_report_text = get_kym_event_report_text
        # Cache visibility per column; seed from config-only initial visibility if provided,
        # otherwise start with all columns visible.
        if initial_visibility is not None:
            self._visible_cache: dict[str, bool] = {
                c: bool(initial_visibility.get(c, True)) for c in self._toggleable_columns
            }
        else:
            self._visible_cache: dict[str, bool] = {c: True for c in self._toggleable_columns}

    def build(self) -> None:
        """Populate the current context menu (call only from grid's contextmenu handler).

        Adds top-level items from FILE_TABLE_CONTEXT_MENU_ITEMS, then a separator
        and a column-visibility section: one item per toggleable column (with ✓ when
        visible), then Show all / Hide all. If get_grid() returns None, the column
        section is omitted.
        """
        for item in FILE_TABLE_CONTEXT_MENU_ITEMS:
            action_id = item["id"]
            label = item["label"]
            ui.menu_item(
                label,
                on_click=lambda a=action_id: self._handle_action(a),
            )

        grid = self._get_grid()
        if grid is None or not self._toggleable_columns:
            return

        ui.separator()
        for col in self._toggleable_columns:
            visible = self._visible_cache.get(col, True)
            label = (_COLUMN_VISIBLE_PREFIX if visible else "") + col
            ui.menu_item(
                label,
                on_click=lambda c=col: self._toggle_column(grid, c),
            )
        ui.separator()
        ui.menu_item("Show all", on_click=lambda: self._show_all(grid))
        ui.menu_item("Hide all", on_click=lambda: self._hide_all(grid))

    def _handle_action(self, action: str) -> None:
        """Handle top-level context menu actions (Reveal, Copy File Table, Copy reports)."""
        if action == "reveal_in_finder":
            selected_file = self._get_selected_file()
            if selected_file is None:
                logger.warning("No file selected for context menu action: %s", action)
                return
            path = getattr(selected_file, "path", None)
            if path is None:
                logger.warning("Selected file has no path for Reveal In Finder")
                return
            logger.info("Reveal In Finder: %s", path)
            reveal_in_file_manager(path)
        elif action == "copy_file_table":
            table_text = self._get_table_text()
            if table_text:
                copy_to_clipboard(table_text)
                logger.info("File table copied to clipboard")
                ui.notify("File table copied to clipboard", type="positive")
            else:
                logger.warning("No table data to copy")
        elif action == "copy_radon_report":
            if self._get_radon_report_text is None:
                logger.warning("Radon report copy not available")
                return
            text = self._get_radon_report_text()
            if text:
                copy_to_clipboard(text)
                logger.info("Radon report copied to clipboard")
                ui.notify("Radon report copied to clipboard", type="positive")
            else:
                logger.warning("No radon report data to copy")
        elif action == "copy_kym_event_report":
            if self._get_kym_event_report_text is None:
                logger.warning("Kym event report copy not available")
                return
            text = self._get_kym_event_report_text()
            if text:
                copy_to_clipboard(text)
                logger.info("Kym event report copied to clipboard")
                ui.notify("Kym event report copied to clipboard", type="positive")
            else:
                logger.warning("No kym event report data to copy")
        else:
            logger.warning("Unknown context menu action: %s", action)

    def _toggle_column(self, grid: Any, col: str) -> None:
        """Toggle one column's visibility and update the grid."""
        self._visible_cache[col] = not self._visible_cache.get(col, True)
        try:
            grid.run_grid_method(
                "setColumnsVisible",
                [col],
                self._visible_cache[col],
            )
        except RuntimeError:
            pass

    def _show_all(self, grid: Any) -> None:
        """Set all toggleable columns visible."""
        for c in self._toggleable_columns:
            self._visible_cache[c] = True
        try:
            grid.run_grid_method("setColumnsVisible", self._toggleable_columns, True)
        except RuntimeError:
            pass

    def _hide_all(self, grid: Any) -> None:
        """Set all toggleable columns hidden."""
        for c in self._toggleable_columns:
            self._visible_cache[c] = False
        try:
            grid.run_grid_method("setColumnsVisible", self._toggleable_columns, False)
        except RuntimeError:
            pass
