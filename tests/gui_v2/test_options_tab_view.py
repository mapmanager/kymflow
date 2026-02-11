"""Tests for OptionsTabView in GUI v2."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from kymflow.gui_v2.app_config import AppConfig, DEFAULT_FOLDER_DEPTH
from kymflow.gui_v2.app_context import AppContext
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.views.options_tab_view import OptionsTabView


def test_options_tab_syncs_folder_depth_on_save(tmp_path: Path) -> None:
    """Test that OptionsTabView syncs app_state.folder_depth when saving settings."""
    # Create app_config with custom folder_depth
    cfg_path = tmp_path / "app_config.json"
    app_config = AppConfig.load(config_path=cfg_path)
    app_config.set_attribute("folder_depth", 6)
    
    # Create app_state with different folder_depth
    app_state = AppState()
    app_state.folder_depth = 2  # Different from app_config
    
    # Create mock context
    context = MagicMock(spec=AppContext)
    context.app_config = app_config
    context.app_state = app_state
    
    # Create OptionsTabView
    view = OptionsTabView(app_config=app_config, context=context)
    
    # Mock _save_all_configs to return success
    with patch("kymflow.gui_v2.views.options_tab_view._save_all_configs", return_value=True):
        # Mock ui.notify to avoid UI calls
        with patch("kymflow.gui_v2.views.options_tab_view.ui.notify"):
            # Call save settings
            view._on_save_settings()
    
    # Verify app_state.folder_depth was synced from app_config
    assert app_state.folder_depth == 6
    assert app_config.get_attribute("folder_depth") == 6


def test_options_tab_syncs_folder_depth_on_save_with_default(tmp_path: Path) -> None:
    """Test that OptionsTabView syncs app_state.folder_depth to default when app_config has default."""
    # Create app_config with default folder_depth
    cfg_path = tmp_path / "app_config.json"
    app_config = AppConfig.load(config_path=cfg_path)
    # Don't set folder_depth - should use default (4)
    
    # Create app_state with different folder_depth
    app_state = AppState()
    app_state.folder_depth = 1  # Different from default
    
    # Create mock context
    context = MagicMock(spec=AppContext)
    context.app_config = app_config
    context.app_state = app_state
    
    # Create OptionsTabView
    view = OptionsTabView(app_config=app_config, context=context)
    
    # Mock _save_all_configs to return success
    with patch("kymflow.gui_v2.views.options_tab_view._save_all_configs", return_value=True):
        # Mock ui.notify to avoid UI calls
        with patch("kymflow.gui_v2.views.options_tab_view.ui.notify"):
            # Call save settings
            view._on_save_settings()
    
    # Verify app_state.folder_depth was synced to default
    assert app_state.folder_depth == DEFAULT_FOLDER_DEPTH
    assert app_config.get_attribute("folder_depth") == DEFAULT_FOLDER_DEPTH


def test_options_tab_syncs_folder_depth_after_changing_value(tmp_path: Path) -> None:
    """Test that OptionsTabView syncs app_state.folder_depth after user changes folder_depth value."""
    # Create app_config
    cfg_path = tmp_path / "app_config.json"
    app_config = AppConfig.load(config_path=cfg_path)
    
    # Create app_state
    app_state = AppState()
    app_state.folder_depth = 3
    
    # Create mock context
    context = MagicMock(spec=AppContext)
    context.app_config = app_config
    context.app_state = app_state
    
    # Create OptionsTabView
    view = OptionsTabView(app_config=app_config, context=context)
    
    # Simulate user changing folder_depth value
    view._on_value_change("folder_depth", 8)
    assert app_config.get_attribute("folder_depth") == 8
    assert app_state.folder_depth == 3  # Not synced yet
    
    # Mock _save_all_configs to return success
    with patch("kymflow.gui_v2.views.options_tab_view._save_all_configs", return_value=True):
        # Mock ui.notify to avoid UI calls
        with patch("kymflow.gui_v2.views.options_tab_view.ui.notify"):
            # Call save settings - this should sync
            view._on_save_settings()
    
    # Verify app_state.folder_depth was synced after save
    assert app_state.folder_depth == 8
    assert app_config.get_attribute("folder_depth") == 8


def test_options_tab_handles_save_failure(tmp_path: Path) -> None:
    """Test that OptionsTabView handles save failure gracefully."""
    # Create app_config
    cfg_path = tmp_path / "app_config.json"
    app_config = AppConfig.load(config_path=cfg_path)
    app_config.set_attribute("folder_depth", 5)
    
    # Create app_state
    app_state = AppState()
    app_state.folder_depth = 2
    
    # Create mock context
    context = MagicMock(spec=AppContext)
    context.app_config = app_config
    context.app_state = app_state
    
    # Create OptionsTabView
    view = OptionsTabView(app_config=app_config, context=context)
    
    # Mock _save_all_configs to return failure
    with patch("kymflow.gui_v2.views.options_tab_view._save_all_configs", return_value=False):
        # Mock ui.notify to avoid UI calls
        with patch("kymflow.gui_v2.views.options_tab_view.ui.notify"):
            # Call save settings
            view._on_save_settings()
    
    # Verify app_state.folder_depth was NOT synced on failure
    assert app_state.folder_depth == 2  # Unchanged
    assert app_config.get_attribute("folder_depth") == 5  # Still set in config


def test_options_tab_handles_missing_app_state(tmp_path: Path) -> None:
    """Test that OptionsTabView handles missing app_state gracefully."""
    # Create app_config
    cfg_path = tmp_path / "app_config.json"
    app_config = AppConfig.load(config_path=cfg_path)
    
    # Create mock context without app_state
    context = MagicMock(spec=AppContext)
    context.app_config = app_config
    context.app_state = None  # Missing app_state
    
    # Create OptionsTabView
    view = OptionsTabView(app_config=app_config, context=context)
    
    # Mock _save_all_configs to return success
    with patch("kymflow.gui_v2.views.options_tab_view._save_all_configs", return_value=True):
        # Mock ui.notify to avoid UI calls
        with patch("kymflow.gui_v2.views.options_tab_view.ui.notify"):
            # Call save settings - should not crash
            view._on_save_settings()
    
    # Should complete without error (hasattr check prevents AttributeError)
