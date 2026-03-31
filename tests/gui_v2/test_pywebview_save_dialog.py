"""Tests for pywebview save dialog helper."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from kymflow.gui_v2._pywebview import _prompt_for_save_path


def test_prompt_for_save_path_returns_selected_path() -> None:
    """Test save dialog helper returns first selected path."""
    mock_main_window = MagicMock()
    async def _dialog(*args, **kwargs):
        return ("/tmp/out.csv",)
    mock_main_window.create_file_dialog = _dialog

    mock_native = MagicMock()
    mock_native.main_window = mock_main_window

    class _MockFileDialog:
        SAVE = "save"

    mock_webview = MagicMock()
    mock_webview.FileDialog = _MockFileDialog

    with patch("kymflow.gui_v2._pywebview.app") as mock_app:
        mock_app.native = mock_native
        with patch("kymflow.gui_v2._pywebview.AppContext") as mock_ctx:
            mock_ctx.return_value.native_ui_gate = None
            with patch.dict("sys.modules", {"webview": mock_webview}):
                result = asyncio.run(
                    _prompt_for_save_path(
                        initial=Path("/tmp"),
                        suggested_filename="kym_event_db.csv",
                        file_extension=".csv",
                    )
                )
    assert result == "/tmp/out.csv"


def test_prompt_for_save_path_returns_none_on_cancel() -> None:
    """Test save dialog helper returns None when user cancels."""
    mock_main_window = MagicMock()
    async def _dialog(*args, **kwargs):
        return None
    mock_main_window.create_file_dialog = _dialog

    mock_native = MagicMock()
    mock_native.main_window = mock_main_window

    class _MockFileDialog:
        SAVE = "save"

    mock_webview = MagicMock()
    mock_webview.FileDialog = _MockFileDialog

    with patch("kymflow.gui_v2._pywebview.app") as mock_app:
        mock_app.native = mock_native
        with patch("kymflow.gui_v2._pywebview.AppContext") as mock_ctx:
            mock_ctx.return_value.native_ui_gate = None
            with patch.dict("sys.modules", {"webview": mock_webview}):
                result = asyncio.run(
                    _prompt_for_save_path(
                        initial=Path("/tmp"),
                    )
                )
    assert result is None
