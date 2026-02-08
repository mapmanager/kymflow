"""Tests for FolderSelectorView CSV functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kymflow.core.user_config import UserConfig
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_folder import SelectPathEvent
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.views.folder_selector_view import FolderSelectorView, PathType


@pytest.fixture
def bus() -> EventBus:
    """Create an EventBus instance."""
    from kymflow.gui_v2.bus import EventBus, BusConfig
    return EventBus(client_id="test-client", config=BusConfig(trace=False))


@pytest.fixture
def app_state() -> AppState:
    """Create a fresh AppState instance."""
    return AppState()


@pytest.fixture
def user_config(tmp_path: Path) -> UserConfig:
    """Create a UserConfig instance."""
    cfg_path = tmp_path / "user_config.json"
    return UserConfig.load(config_path=cfg_path)


def test_build_recent_menu_includes_csvs(
    bus: EventBus, app_state: AppState, user_config: UserConfig, tmp_path: Path
) -> None:
    """Test _build_recent_menu_data() includes CSV paths."""
    view = FolderSelectorView(bus, app_state, user_config=user_config)
    
    csv1 = tmp_path / "csv1.csv"
    csv2 = tmp_path / "csv2.csv"
    csv1.write_text("path\n/file1.tif")
    csv2.write_text("path\n/file2.tif")
    
    user_config.push_recent_csv(csv1)
    user_config.push_recent_csv(csv2)
    
    folder_paths, file_paths, csv_paths = view._build_recent_menu_data()
    
    assert len(csv_paths) == 2
    assert str(csv2.resolve(strict=False)) in csv_paths
    assert str(csv1.resolve(strict=False)) in csv_paths


def test_on_recent_path_selected_csv(
    bus: EventBus, app_state: AppState, user_config: UserConfig, tmp_path: Path
) -> None:
    """Test _on_recent_path_selected() emits SelectPathEvent for CSV (without csv_path field)."""
    view = FolderSelectorView(bus, app_state, user_config=user_config)
    
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("path\n/file1.tif")
    
    emitted_events = []
    def capture_event(e):
        emitted_events.append(e)
    bus.subscribe_intent(SelectPathEvent, capture_event)
    
    view._on_recent_path_selected(str(csv_file), is_csv=True)
    
    # Should emit SelectPathEvent
    assert len(emitted_events) == 1
    assert isinstance(emitted_events[0], SelectPathEvent)
    assert emitted_events[0].new_path == str(csv_file)
    # Should NOT have csv_path field (auto-detected by controller)
    assert not hasattr(emitted_events[0], 'csv_path') or getattr(emitted_events[0], 'csv_path', None) is None


def test_on_recent_path_selected_csv_auto_detection(
    bus: EventBus, app_state: AppState, user_config: UserConfig, tmp_path: Path
) -> None:
    """Test _on_recent_path_selected() auto-detects CSV from path extension."""
    view = FolderSelectorView(bus, app_state, user_config=user_config)
    
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("path\n/file1.tif")
    
    emitted_events = []
    def capture_event(e):
        emitted_events.append(e)
    bus.subscribe_intent(SelectPathEvent, capture_event)
    
    # Don't pass is_csv=True - should auto-detect from extension
    view._on_recent_path_selected(str(csv_file), is_csv=False)
    
    # Should emit SelectPathEvent
    assert len(emitted_events) == 1
    assert isinstance(emitted_events[0], SelectPathEvent)
    assert emitted_events[0].new_path == str(csv_file)


def test_on_open_csv_emits_event(
    bus: EventBus, app_state: AppState, user_config: UserConfig, tmp_path: Path
) -> None:
    """Test _on_open_path(PathType.CSV) emits SelectPathEvent when CSV is selected.
    
    Note: We don't test pywebview directly - we mock _prompt_for_path
    which is the actual function that handles the file dialog. This follows the
    same pattern as other tests that don't test native UI components directly.
    """
    view = FolderSelectorView(bus, app_state, user_config=user_config)
    
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("path\n/file1.tif")
    
    emitted_events = []
    def capture_event(e):
        emitted_events.append(e)
    bus.subscribe_intent(SelectPathEvent, capture_event)
    
    # Mock _prompt_for_path to return CSV path (this bypasses all pywebview checks)
    # This is the same approach used in other tests - we test the logic, not the native UI
    with patch("kymflow.gui_v2.views.folder_selector_view._prompt_for_path") as mock_prompt:
        # Make it return the CSV path (it's async, but return_value works for awaited calls)
        async def mock_prompt_async(*args, **kwargs):
            return str(csv_file)
        mock_prompt.side_effect = mock_prompt_async
        
        # Mock ui.notify to avoid UI calls
        with patch("kymflow.gui_v2.views.folder_selector_view.ui.notify"):
            # Mock the webview import to succeed (patch at builtins level)
            import builtins
            original_import = builtins.__import__
            
            def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "webview":
                    # Return a mock webview module
                    mock_webview_module = MagicMock()
                    mock_webview_module.windows = [MagicMock()]  # Simulate windows available
                    return mock_webview_module
                return original_import(name, globals, locals, fromlist, level)
            
            # Mock app.native.main_window
            with patch("kymflow.gui_v2.views.folder_selector_view.app") as mock_app:
                mock_native = MagicMock()
                mock_native.main_window = MagicMock()
                mock_app.native = mock_native
                
                with patch("builtins.__import__", side_effect=mock_import):
                    import asyncio
                    asyncio.run(view._on_open_path(PathType.CSV))
        
        # Should emit SelectPathEvent
        assert len(emitted_events) == 1, f"Expected 1 event, got {len(emitted_events)}: {emitted_events}"
        assert isinstance(emitted_events[0], SelectPathEvent)
        assert emitted_events[0].new_path == str(csv_file)
        # Should NOT have csv_path field
        assert not hasattr(emitted_events[0], 'csv_path') or getattr(emitted_events[0], 'csv_path', None) is None
