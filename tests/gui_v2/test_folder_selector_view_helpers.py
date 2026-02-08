"""Tests for FolderSelectorView helper functions and PathType enum."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kymflow.core.user_config import UserConfig
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events_folder import SelectPathEvent
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.views.folder_selector_view import (
    FolderSelectorView,
    PathType,
    _validate_native_mode_for_dialog,
)


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


# ============================================================================
# PathType Enum Tests
# ============================================================================

def test_path_type_enum_values() -> None:
    """Test that PathType enum has correct values."""
    assert PathType.FOLDER == "folder"
    assert PathType.FILE == "file"
    assert PathType.CSV == "csv"


def test_path_type_enum_string_compatibility() -> None:
    """Test that PathType enum values work as strings."""
    # Should be comparable to strings directly (str, Enum allows this)
    assert PathType.FOLDER == "folder"
    assert PathType.FILE == "file"
    assert PathType.CSV == "csv"
    
    # Should have .value property that returns the string
    assert PathType.FOLDER.value == "folder"
    assert PathType.FILE.value == "file"
    assert PathType.CSV.value == "csv"
    
    # Can be used in string contexts via .value
    assert f"{PathType.FOLDER.value}" == "folder"
    assert f"{PathType.FILE.value}" == "file"
    assert f"{PathType.CSV.value}" == "csv"


def test_path_type_enum_extensibility() -> None:
    """Test that PathType enum can be extended (type safety check)."""
    # Verify all expected values exist
    assert hasattr(PathType, "FOLDER")
    assert hasattr(PathType, "FILE")
    assert hasattr(PathType, "CSV")
    
    # Verify enum can be used in type hints
    def test_function(path_type: PathType) -> str:
        return path_type.value
    
    assert test_function(PathType.FOLDER) == "folder"
    assert test_function(PathType.FILE) == "file"
    assert test_function(PathType.CSV) == "csv"


# ============================================================================
# Native Validation Helper Tests
# ============================================================================

def test_validate_native_mode_for_dialog_webview_import_fails() -> None:
    """Test _validate_native_mode_for_dialog when webview import fails."""
    with patch("builtins.__import__", side_effect=ImportError("No module named 'webview'")):
        is_available, error_msg = _validate_native_mode_for_dialog(PathType.FOLDER)
        assert is_available is False
        assert error_msg is not None
        assert "native mode" in error_msg.lower()


def test_validate_native_mode_for_dialog_no_windows() -> None:
    """Test _validate_native_mode_for_dialog when no windows available."""
    mock_webview = MagicMock()
    mock_webview.windows = []
    
    with patch("builtins.__import__", return_value=mock_webview):
        with patch("kymflow.gui_v2.views.folder_selector_view.app") as mock_app:
            mock_app.native = None
            is_available, error_msg = _validate_native_mode_for_dialog(PathType.FILE)
            assert is_available is False
            assert error_msg is not None


def test_validate_native_mode_for_dialog_success() -> None:
    """Test _validate_native_mode_for_dialog when native mode is available."""
    mock_webview = MagicMock()
    mock_webview.windows = [MagicMock()]
    
    with patch("builtins.__import__", return_value=mock_webview):
        with patch("kymflow.gui_v2.views.folder_selector_view.app") as mock_app:
            mock_native = MagicMock()
            mock_native.main_window = MagicMock()
            mock_app.native = mock_native
            is_available, error_msg = _validate_native_mode_for_dialog(PathType.CSV)
            assert is_available is True
            assert error_msg is None


def test_validate_native_mode_for_dialog_all_path_types() -> None:
    """Test _validate_native_mode_for_dialog with all PathType values."""
    mock_webview = MagicMock()
    mock_webview.windows = [MagicMock()]
    
    with patch("builtins.__import__", return_value=mock_webview):
        with patch("kymflow.gui_v2.views.folder_selector_view.app") as mock_app:
            mock_native = MagicMock()
            mock_native.main_window = MagicMock()
            mock_app.native = mock_native
            
            for path_type in PathType:
                is_available, error_msg = _validate_native_mode_for_dialog(path_type)
                assert is_available is True
                assert error_msg is None


# ============================================================================
# Depth Calculation Helper Tests
# ============================================================================

def test_calculate_depth_for_path_folder(bus: EventBus, app_state: AppState) -> None:
    """Test _calculate_depth_for_path for FOLDER type."""
    view = FolderSelectorView(bus, app_state, user_config=None)
    view.render()
    
    # Set depth input value
    if view._depth_input is not None:
        view._depth_input.value = 5
    
    depth = view._calculate_depth_for_path(PathType.FOLDER)
    assert depth == 5


def test_calculate_depth_for_path_folder_no_input(bus: EventBus, app_state: AppState) -> None:
    """Test _calculate_depth_for_path for FOLDER when no depth input."""
    app_state.folder_depth = 3
    view = FolderSelectorView(bus, app_state, user_config=None)
    view.render()
    
    # Remove depth input
    view._depth_input = None
    
    depth = view._calculate_depth_for_path(PathType.FOLDER)
    assert depth == 3


def test_calculate_depth_for_path_file(bus: EventBus, app_state: AppState) -> None:
    """Test _calculate_depth_for_path for FILE type."""
    view = FolderSelectorView(bus, app_state, user_config=None)
    view.render()
    
    depth = view._calculate_depth_for_path(PathType.FILE)
    assert depth is None


def test_calculate_depth_for_path_csv(bus: EventBus, app_state: AppState) -> None:
    """Test _calculate_depth_for_path for CSV type."""
    view = FolderSelectorView(bus, app_state, user_config=None)
    view.render()
    
    depth = view._calculate_depth_for_path(PathType.CSV)
    assert depth is None
