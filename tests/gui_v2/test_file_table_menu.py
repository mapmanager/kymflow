"""Tests for FileTableContextMenu and file table context menu config."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from kymflow.gui_v2.menus.file_table_menu import (
    FILE_TABLE_CONTEXT_MENU_ITEMS,
    FileTableContextMenu,
)
from kymflow.gui_v2.views.file_table_view import (
    get_file_table_initial_column_visibility,
    get_file_table_toggleable_column_fields,
)


def test_file_table_context_menu_items_config() -> None:
    """FILE_TABLE_CONTEXT_MENU_ITEMS contains expected top-level actions."""
    ids = [item["id"] for item in FILE_TABLE_CONTEXT_MENU_ITEMS]
    assert "reveal_in_finder" in ids
    assert "copy_file_table" in ids
    assert "copy_radon_report" in ids
    assert "copy_kym_event_report" in ids
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
    menu = FileTableContextMenu(
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=["A", "B"],
    )
    # build() calls ui.menu_item and ui.separator; mock them so we don't need a NiceGUI context.
    with patch("kymflow.gui_v2.menus.file_table_menu.ui.menu_item"), patch(
        "kymflow.gui_v2.menus.file_table_menu.ui.separator"
    ):
        menu.build()
    # Top-level items were added (we cannot trigger clicks without UI).


def test_file_table_context_menu_column_toggle_calls_grid() -> None:
    """_toggle_column updates cache and calls grid.run_grid_method with setColumnsVisible."""
    grid = MagicMock()
    menu = FileTableContextMenu(
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
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
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
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
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
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
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=toggleable,
    )
    assert menu._visible_cache == {"a": True, "b": True}


def test_file_table_context_menu_initial_visibility_seeded_from_config() -> None:
    """Visible cache honors initial_visibility mapping when provided."""
    toggleable = ["File Name", "Parent Folder"]
    visibility = get_file_table_initial_column_visibility()
    menu = FileTableContextMenu(
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=toggleable,
        initial_visibility=visibility,
    )
    # "Parent Folder" has hide=True in the default columns, so should start hidden.
    assert menu._visible_cache["File Name"] is True
    assert menu._visible_cache["Parent Folder"] is False


def test_handle_action_copy_file_table_calls_copy_to_clipboard() -> None:
    """_handle_action('copy_file_table') calls get_table_text and copy_to_clipboard when text non-empty."""
    table_text = "col1\tcol2\nv1\tv2"
    get_table_text = MagicMock(return_value=table_text)
    menu = FileTableContextMenu(
        get_selected_file=lambda: None,
        get_table_text=get_table_text,
        get_grid=lambda: None,
        toggleable_columns=[],
    )
    with patch("kymflow.gui_v2.menus.file_table_menu.copy_to_clipboard") as mock_copy:
        menu._handle_action("copy_file_table")
    get_table_text.assert_called_once()
    mock_copy.assert_called_once_with(table_text)


def test_handle_action_copy_file_table_empty_does_not_call_copy() -> None:
    """_handle_action('copy_file_table') does not call copy_to_clipboard when get_table_text returns empty."""
    menu = FileTableContextMenu(
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=[],
    )
    with patch("kymflow.gui_v2.menus.file_table_menu.copy_to_clipboard") as mock_copy:
        menu._handle_action("copy_file_table")
    mock_copy.assert_not_called()


def test_handle_action_reveal_in_finder_calls_reveal_in_file_manager() -> None:
    """_handle_action('reveal_in_finder') calls reveal_in_file_manager with selected file path."""
    fake_path = "/some/folder/file.tif"
    selected = MagicMock()
    selected.path = fake_path
    menu = FileTableContextMenu(
        get_selected_file=lambda: selected,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=[],
    )
    with patch("kymflow.gui_v2.menus.file_table_menu.reveal_in_file_manager") as mock_reveal:
        menu._handle_action("reveal_in_finder")
    mock_reveal.assert_called_once_with(fake_path)


def test_handle_action_reveal_in_finder_no_file_does_not_reveal() -> None:
    """_handle_action('reveal_in_finder') does not call reveal_in_file_manager when no file selected."""
    menu = FileTableContextMenu(
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=[],
    )
    with patch("kymflow.gui_v2.menus.file_table_menu.reveal_in_file_manager") as mock_reveal:
        menu._handle_action("reveal_in_finder")
    mock_reveal.assert_not_called()


def test_handle_action_reveal_in_finder_no_path_does_not_reveal() -> None:
    """_handle_action('reveal_in_finder') does not call reveal when selected file has no path."""
    selected = MagicMock(spec=[])  # no path attribute
    menu = FileTableContextMenu(
        get_selected_file=lambda: selected,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=[],
    )
    with patch("kymflow.gui_v2.menus.file_table_menu.reveal_in_file_manager") as mock_reveal:
        menu._handle_action("reveal_in_finder")
    mock_reveal.assert_not_called()


def test_handle_action_copy_radon_report_calls_copy_to_clipboard() -> None:
    """_handle_action('copy_radon_report') calls get_radon_report_text and copy_to_clipboard when text non-empty."""
    report_text = "roi_id,vel_mean\n1,0.5"
    get_radon = MagicMock(return_value=report_text)
    menu = FileTableContextMenu(
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=[],
        get_radon_report_text=get_radon,
    )
    with patch("kymflow.gui_v2.menus.file_table_menu.copy_to_clipboard") as mock_copy:
        menu._handle_action("copy_radon_report")
    get_radon.assert_called_once()
    mock_copy.assert_called_once_with(report_text)


def test_handle_action_copy_radon_report_not_available_does_not_copy() -> None:
    """_handle_action('copy_radon_report') does not call copy_to_clipboard when get_radon_report_text is None."""
    menu = FileTableContextMenu(
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=[],
        get_radon_report_text=None,
    )
    with patch("kymflow.gui_v2.menus.file_table_menu.copy_to_clipboard") as mock_copy:
        menu._handle_action("copy_radon_report")
    mock_copy.assert_not_called()


def test_handle_action_copy_radon_report_empty_does_not_copy() -> None:
    """_handle_action('copy_radon_report') does not call copy_to_clipboard when text is empty."""
    menu = FileTableContextMenu(
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=[],
        get_radon_report_text=lambda: "",
    )
    with patch("kymflow.gui_v2.menus.file_table_menu.copy_to_clipboard") as mock_copy:
        menu._handle_action("copy_radon_report")
    mock_copy.assert_not_called()


def test_handle_action_copy_kym_event_report_calls_copy_to_clipboard() -> None:
    """_handle_action('copy_kym_event_report') calls get_kym_event_report_text and copy_to_clipboard when text non-empty."""
    report_text = "path,roi_id,t_start\n/p.tif,1,0.1"
    get_kym = MagicMock(return_value=report_text)
    menu = FileTableContextMenu(
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=[],
        get_kym_event_report_text=get_kym,
    )
    with patch("kymflow.gui_v2.menus.file_table_menu.copy_to_clipboard") as mock_copy:
        menu._handle_action("copy_kym_event_report")
    get_kym.assert_called_once()
    mock_copy.assert_called_once_with(report_text)


def test_handle_action_copy_kym_event_report_not_available_does_not_copy() -> None:
    """_handle_action('copy_kym_event_report') does not call copy when get_kym_event_report_text is None."""
    menu = FileTableContextMenu(
        get_selected_file=lambda: None,
        get_table_text=lambda: "",
        get_grid=lambda: None,
        toggleable_columns=[],
        get_kym_event_report_text=None,
    )
    with patch("kymflow.gui_v2.menus.file_table_menu.copy_to_clipboard") as mock_copy:
        menu._handle_action("copy_kym_event_report")
    mock_copy.assert_not_called()


def test_handle_action_unknown_action_does_not_call_copy_or_reveal() -> None:
    """_handle_action with unknown action id does not call copy_to_clipboard or reveal_in_file_manager."""
    menu = FileTableContextMenu(
        get_selected_file=lambda: MagicMock(path="/x"),
        get_table_text=lambda: "table",
        get_grid=lambda: None,
        toggleable_columns=[],
        get_radon_report_text=lambda: "radon",
        get_kym_event_report_text=lambda: "kym",
    )
    with patch("kymflow.gui_v2.menus.file_table_menu.copy_to_clipboard") as mock_copy:
        with patch("kymflow.gui_v2.menus.file_table_menu.reveal_in_file_manager") as mock_reveal:
            menu._handle_action("unknown_action_id")
    mock_copy.assert_not_called()
    mock_reveal.assert_not_called()
