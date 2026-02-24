"""File table right-click context menu: config-driven items and column visibility.

This module provides a reusable context menu for the file table grid. The menu
is rebuilt on each open (via CustomAgGrid_v2's on_build_context_menu), so content
can be dynamic (e.g. column visibility state).

Usage:
    menu = FileTableContextMenu(
        on_action=page._on_context_menu,
        get_grid=lambda: file_table_view._grid,
        toggleable_columns=get_file_table_toggleable_column_fields(),
    )
    file_table_view.set_context_menu_builder(menu.build)
"""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

# Checkmark prefix for visible columns in the column-visibility section.
_COLUMN_VISIBLE_PREFIX = "✓ "


# Top-level menu items (action id and display label). Order is preserved.
FILE_TABLE_CONTEXT_MENU_ITEMS = [
    {"id": "reveal_in_finder", "label": "Reveal In Finder"},
    {"id": "copy_file_table", "label": "Copy File Table"},
    {"id": "other", "label": "Other..."},
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
        on_action: Callable[[str], None],
        get_grid: Callable[[], Any],
        toggleable_columns: list[str],
    ) -> None:
        """Create a file table context menu builder.

        Args:
            on_action: Called with the action id when a top-level item is chosen
                (e.g. 'reveal_in_finder', 'copy_file_table', 'other').
            get_grid: Callable that returns the CustomAgGrid_v2 grid instance (or None
                if the grid is not yet created). Used for column visibility toggles.
            toggleable_columns: List of column field ids that can be shown/hidden.
                Typically from get_file_table_toggleable_column_fields().
        """
        self._on_action = on_action
        self._get_grid = get_grid
        self._toggleable_columns = list(toggleable_columns)
        # Cache visibility per column; start with all visible.
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
                on_click=lambda a=action_id: self._on_action(a),
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
