"""Tests for FileTableContextMenu and file table context menu config."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from kymflow.gui_v2.menus.file_table_menu import (
    FILE_TABLE_CONTEXT_MENU_ITEMS,
    FileTableContextMenu,
)
from kymflow.gui_v2.views.file_table_view import get_file_table_toggleable_column_fields


def test_file_table_context_menu_items_config() -> None:
    """FILE_TABLE_CONTEXT_MENU_ITEMS contains expected top-level actions."""
    ids = [item["id"] for item in FILE_TABLE_CONTEXT_MENU_ITEMS]
    assert "reveal_in_finder" in ids
    assert "copy_file_table" in ids
    assert "other" in ids
    for item in FILE_TABLE_CONTEXT_MENU_ITEMS:
        assert "id" in item
        assert "label" in item
        assert isinstance(item["id"], str)
        assert isinstance(item["label"], str)


def test_get_file_table_toggleable_column_fields_non_empty() -> None:
    """Toggleable columns list is non-empty and includes expected file table columns."""
    fields = get_file_table_toggleable_column_fields()
    assert len(fields) > 0
    assert "File Name" in fields
    assert "note" in fields
    assert "accepted" in fields


def test_file_table_context_menu_build_without_grid() -> None:
    """build() runs without error when get_grid returns None (no column section)."""
    actions: list[str] = []

    def on_action(action_id: str) -> None:
        actions.append(action_id)

    menu = FileTableContextMenu(
        on_action=on_action,
        get_grid=lambda: None,
        toggleable_columns=["A", "B"],
    )
    # build() calls ui.menu_item and ui.separator; mock them so we don't need a NiceGUI context.
    with patch("kymflow.gui_v2.menus.file_table_menu.ui.menu_item"), patch(
        "kymflow.gui_v2.menus.file_table_menu.ui.separator"
    ):
        menu.build()
    # Top-level items were added (we cannot trigger clicks without UI).
    assert len(actions) == 0


def test_file_table_context_menu_column_toggle_calls_grid() -> None:
    """_toggle_column updates cache and calls grid.run_grid_method with setColumnsVisible."""
    grid = MagicMock()
    menu = FileTableContextMenu(
        on_action=lambda a: None,
        get_grid=lambda: grid,
        toggleable_columns=["col1", "col2"],
    )
    menu._toggle_column(grid, "col1")
    assert menu._visible_cache["col1"] is False
    grid.run_grid_method.assert_called_once_with("setColumnsVisible", ["col1"], False)
    grid.reset_mock()
    menu._toggle_column(grid, "col1")
    assert menu._visible_cache["col1"] is True
    grid.run_grid_method.assert_called_once_with("setColumnsVisible", ["col1"], True)


def test_file_table_context_menu_show_all_calls_grid() -> None:
    """_show_all sets all visible and calls setColumnsVisible(columns, True)."""
    grid = MagicMock()
    toggleable = ["c1", "c2"]
    menu = FileTableContextMenu(
        on_action=lambda a: None,
        get_grid=lambda: grid,
        toggleable_columns=toggleable,
    )
    menu._visible_cache["c1"] = False
    menu._show_all(grid)
    assert menu._visible_cache["c1"] is True
    assert menu._visible_cache["c2"] is True
    grid.run_grid_method.assert_called_once_with("setColumnsVisible", toggleable, True)


def test_file_table_context_menu_hide_all_calls_grid() -> None:
    """_hide_all sets all hidden and calls setColumnsVisible(columns, False)."""
    grid = MagicMock()
    toggleable = ["c1", "c2"]
    menu = FileTableContextMenu(
        on_action=lambda a: None,
        get_grid=lambda: grid,
        toggleable_columns=toggleable,
    )
    menu._hide_all(grid)
    assert menu._visible_cache["c1"] is False
    assert menu._visible_cache["c2"] is False
    grid.run_grid_method.assert_called_once_with("setColumnsVisible", toggleable, False)


def test_file_table_context_menu_visible_cache_initialized() -> None:
    """Visible cache starts with all columns True."""
    toggleable = ["a", "b"]
    menu = FileTableContextMenu(
        on_action=lambda a: None,
        get_grid=lambda: None,
        toggleable_columns=toggleable,
    )
    assert menu._visible_cache == {"a": True, "b": True}
