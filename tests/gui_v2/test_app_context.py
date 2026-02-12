"""Tests for AppContext behavior in GUI v2."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from kymflow.core.plotting.theme import ThemeMode
from kymflow.gui_v2 import app_context
from kymflow.gui_v2.app_context import AppContext, THEME_STORAGE_KEY
from kymflow.gui_v2.app_config import AppConfig, DEFAULT_FOLDER_DEPTH, DEFAULT_TEXT_SIZE


class DummyAppState:
    """Minimal AppState stub for theme updates."""

    def __init__(self) -> None:
        self.theme_calls: list[ThemeMode] = []

    def set_theme(self, mode: ThemeMode) -> None:
        self.theme_calls.append(mode)


class DummyStorage:
    """Simple storage stub mimicking nicegui.app.storage."""

    def __init__(self) -> None:
        self.user: dict[str, bool] = {}


class DummyDarkMode:
    """Simple dark mode controller stub."""

    def __init__(self) -> None:
        self.value = False


def test_init_dark_mode_reads_storage(monkeypatch) -> None:
    """init_dark_mode_for_page syncs storage value and AppState theme."""
    storage = DummyStorage()
    storage.user[THEME_STORAGE_KEY] = True
    monkeypatch.setattr(app_context, "app", SimpleNamespace(storage=storage))
    monkeypatch.setattr(app_context.ui, "dark_mode", lambda: DummyDarkMode())

    context = AppContext()
    dummy_state = DummyAppState()
    context.app_state = dummy_state

    dark_mode = context.init_dark_mode_for_page()

    assert dark_mode.value is True
    assert dummy_state.theme_calls[-1] == ThemeMode.DARK


def test_toggle_theme_persists_and_updates_state(monkeypatch) -> None:
    """toggle_theme should persist to storage and update AppState."""
    storage = DummyStorage()
    monkeypatch.setattr(app_context, "app", SimpleNamespace(storage=storage))

    context = AppContext()
    dummy_state = DummyAppState()
    context.app_state = dummy_state

    dark_mode = DummyDarkMode()
    dark_mode.value = True

    context.toggle_theme(dark_mode)

    assert dark_mode.value is False
    assert storage.user[THEME_STORAGE_KEY] is False
    assert dummy_state.theme_calls[-1] == ThemeMode.LIGHT


def test_app_context_loads_app_config(tmp_path: Path, monkeypatch) -> None:
    """Test that AppContext loads app_config on initialization."""
    # Reset singleton to ensure fresh initialization
    AppContext._instance = None

    # Create a test app_config file
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    cfg.set_attribute("text_size", "text-lg")
    cfg.save()

    # Mock multiprocessing to ensure we're in main process
    class MockProcess:
        name = "MainProcess"

    monkeypatch.setattr(app_context, "mp", SimpleNamespace(current_process=lambda: MockProcess()))

    # Mock ui with all elements that _setUpGuiDefaults() uses
    def create_mock_ui_element():
        return SimpleNamespace(default_classes=lambda x: None, default_props=lambda x: None)

    mock_ui = SimpleNamespace(
        label=create_mock_ui_element(),
        button=create_mock_ui_element(),
        checkbox=create_mock_ui_element(),
        select=create_mock_ui_element(),
        input=create_mock_ui_element(),
        number=create_mock_ui_element(),
        expansion=create_mock_ui_element(),
        slider=create_mock_ui_element(),
        linear_progress=create_mock_ui_element(),
        menu=create_mock_ui_element(),
        menu_item=create_mock_ui_element(),
        radio=create_mock_ui_element(),
    )

    monkeypatch.setattr(app_context, "ui", mock_ui)

    # Set environment variable to use our test config
    import os
    monkeypatch.setenv("KYMFLOW_APP_CONFIG_PATH", str(cfg_path))

    # Initialize AppContext
    context = AppContext()

    # Verify app_config is loaded
    assert context.app_config is not None
    assert context.app_config.get_attribute("text_size") == "text-lg"


def test_app_context_uses_app_config_text_size(tmp_path: Path, monkeypatch) -> None:
    """Test that AppContext loads app_config with correct text_size."""
    # Reset singleton
    AppContext._instance = None

    # Create app_config with custom text_size
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    cfg.set_attribute("text_size", "text-base")
    cfg.save()

    # Mock multiprocessing
    class MockProcess:
        name = "MainProcess"

    monkeypatch.setattr(app_context, "mp", SimpleNamespace(current_process=lambda: MockProcess()))

    # Mock ui.default_classes to capture calls
    captured_classes = {}

    def mock_default_classes(classes: str) -> None:
        captured_classes["classes"] = classes

    mock_ui = SimpleNamespace()
    mock_ui.label = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)
    mock_ui.button = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)
    mock_ui.checkbox = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)
    mock_ui.select = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)
    mock_ui.input = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)
    mock_ui.number = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)
    mock_ui.expansion = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)
    mock_ui.slider = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)
    mock_ui.linear_progress = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)
    mock_ui.menu = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)
    mock_ui.menu_item = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)
    mock_ui.radio = SimpleNamespace(default_classes=mock_default_classes, default_props=lambda x: None)

    monkeypatch.setattr(app_context, "ui", mock_ui)

    # Set environment variable to use our test config
    import os
    monkeypatch.setenv("KYMFLOW_APP_CONFIG_PATH", str(cfg_path))

    # Initialize AppContext (this will call _setUpGuiDefaults)
    context = AppContext()

    # Verify app_config was loaded with correct value
    assert context.app_config is not None
    assert context.app_config.get_attribute("text_size") == "text-base"

    # Note: We can't easily verify that _setUpGuiDefaults used the value
    # because it sets default_classes which are static methods.
    # But we can verify the config was loaded correctly.


def test_app_context_app_config_none_in_worker_process(monkeypatch) -> None:
    """Test that app_config is None in worker processes."""
    # Reset singleton
    AppContext._instance = None

    # Mock multiprocessing to simulate worker process
    class MockProcess:
        name = "Worker-1"  # Not MainProcess

    monkeypatch.setattr(app_context, "mp", SimpleNamespace(current_process=lambda: MockProcess()))

    # Initialize AppContext
    context = AppContext()

    # In worker process, app_config should be None
    assert context.app_config is None
    assert context.app_state is None
    assert context.user_config is None


def test_app_context_syncs_folder_depth_from_app_config(tmp_path: Path, monkeypatch) -> None:
    """Test that AppContext syncs app_state.folder_depth from app_config on initialization."""
    # Reset singleton to ensure fresh initialization
    AppContext._instance = None

    # Create a test app_config file with custom folder_depth
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    cfg.set_attribute("folder_depth", 7)
    cfg.save()

    # Mock multiprocessing to ensure we're in main process
    class MockProcess:
        name = "MainProcess"

    monkeypatch.setattr(app_context, "mp", SimpleNamespace(current_process=lambda: MockProcess()))

    # Mock ui with all elements that _setUpGuiDefaults() uses
    def create_mock_ui_element():
        return SimpleNamespace(default_classes=lambda x: None, default_props=lambda x: None)

    mock_ui = SimpleNamespace(
        label=create_mock_ui_element(),
        button=create_mock_ui_element(),
        checkbox=create_mock_ui_element(),
        select=create_mock_ui_element(),
        input=create_mock_ui_element(),
        number=create_mock_ui_element(),
        expansion=create_mock_ui_element(),
        slider=create_mock_ui_element(),
        linear_progress=create_mock_ui_element(),
        menu=create_mock_ui_element(),
        menu_item=create_mock_ui_element(),
        radio=create_mock_ui_element(),
    )

    monkeypatch.setattr(app_context, "ui", mock_ui)

    # Set environment variable to use our test config
    import os
    monkeypatch.setenv("KYMFLOW_APP_CONFIG_PATH", str(cfg_path))

    # Initialize AppContext
    context = AppContext()

    # Verify app_state.folder_depth was synced from app_config
    assert context.app_state is not None
    assert context.app_config is not None
    assert context.app_config.get_attribute("folder_depth") == 7
    assert context.app_state.folder_depth == 7


def test_app_context_syncs_folder_depth_default(tmp_path: Path, monkeypatch) -> None:
    """Test that AppContext syncs app_state.folder_depth to default (4) when app_config has default."""
    # Reset singleton to ensure fresh initialization
    AppContext._instance = None

    # Create a test app_config file with default folder_depth (not explicitly set)
    cfg_path = tmp_path / "app_config.json"
    cfg = AppConfig.load(config_path=cfg_path)
    # Don't set folder_depth - should use default
    cfg.save()

    # Mock multiprocessing to ensure we're in main process
    class MockProcess:
        name = "MainProcess"

    monkeypatch.setattr(app_context, "mp", SimpleNamespace(current_process=lambda: MockProcess()))

    # Mock ui with all elements that _setUpGuiDefaults() uses
    def create_mock_ui_element():
        return SimpleNamespace(default_classes=lambda x: None, default_props=lambda x: None)

    mock_ui = SimpleNamespace(
        label=create_mock_ui_element(),
        button=create_mock_ui_element(),
        checkbox=create_mock_ui_element(),
        select=create_mock_ui_element(),
        input=create_mock_ui_element(),
        number=create_mock_ui_element(),
        expansion=create_mock_ui_element(),
        slider=create_mock_ui_element(),
        linear_progress=create_mock_ui_element(),
        menu=create_mock_ui_element(),
        menu_item=create_mock_ui_element(),
        radio=create_mock_ui_element(),
    )

    monkeypatch.setattr(app_context, "ui", mock_ui)

    # Set environment variable to use our test config
    import os
    monkeypatch.setenv("KYMFLOW_APP_CONFIG_PATH", str(cfg_path))

    # Initialize AppContext
    context = AppContext()

    # Verify app_state.folder_depth was synced to default
    assert context.app_state is not None
    assert context.app_config is not None
    assert context.app_config.get_attribute("folder_depth") == DEFAULT_FOLDER_DEPTH
    assert context.app_state.folder_depth == DEFAULT_FOLDER_DEPTH


# ============================================================================
# RuntimeEnvironment Tests
# ============================================================================

def test_runtime_environment_defaults(monkeypatch) -> None:
    """Test RuntimeEnvironment.detect() with no env vars (defaults)."""
    from kymflow.gui_v2.app_context import RuntimeEnvironment
    
    # Clear env vars
    monkeypatch.delenv("KYMFLOW_GUI_NATIVE", raising=False)
    monkeypatch.delenv("KYMFLOW_REMOTE", raising=False)
    
    env = RuntimeEnvironment.detect()
    
    assert env.native_mode is True  # Default
    assert env.is_remote is False  # Default
    assert env.has_file_system_access is True  # native=True OR not remote=True


def test_runtime_environment_native_true_remote_false(monkeypatch) -> None:
    """Test RuntimeEnvironment with native=True, remote=False (local dev)."""
    from kymflow.gui_v2.app_context import RuntimeEnvironment
    
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "1")
    monkeypatch.setenv("KYMFLOW_REMOTE", "0")
    
    env = RuntimeEnvironment.detect()
    
    assert env.native_mode is True
    assert env.is_remote is False
    assert env.has_file_system_access is True


def test_runtime_environment_native_false_remote_false(monkeypatch) -> None:
    """Test RuntimeEnvironment with native=False, remote=False (local browser mode)."""
    from kymflow.gui_v2.app_context import RuntimeEnvironment
    
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "0")
    monkeypatch.setenv("KYMFLOW_REMOTE", "0")
    
    env = RuntimeEnvironment.detect()
    
    assert env.native_mode is False
    assert env.is_remote is False
    assert env.has_file_system_access is True  # Not remote, so has access


def test_runtime_environment_native_false_remote_true(monkeypatch) -> None:
    """Test RuntimeEnvironment with native=False, remote=True (Docker/cloud)."""
    from kymflow.gui_v2.app_context import RuntimeEnvironment
    
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "0")
    monkeypatch.setenv("KYMFLOW_REMOTE", "1")
    
    env = RuntimeEnvironment.detect()
    
    assert env.native_mode is False
    assert env.is_remote is True
    assert env.has_file_system_access is False  # Not native AND remote


def test_runtime_environment_native_true_remote_true(monkeypatch) -> None:
    """Test RuntimeEnvironment with native=True, remote=True (edge case)."""
    from kymflow.gui_v2.app_context import RuntimeEnvironment
    
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "1")
    monkeypatch.setenv("KYMFLOW_REMOTE", "1")
    
    env = RuntimeEnvironment.detect()
    
    assert env.native_mode is True
    assert env.is_remote is True
    assert env.has_file_system_access is True  # Native mode always has access


def test_runtime_environment_env_var_formats(monkeypatch) -> None:
    """Test RuntimeEnvironment accepts various env var formats."""
    from kymflow.gui_v2.app_context import RuntimeEnvironment
    
    # Test various "true" formats
    for true_val in ["1", "true", "True", "TRUE", "yes", "Yes", "YES", "on", "On", "ON"]:
        monkeypatch.setenv("KYMFLOW_GUI_NATIVE", true_val)
        monkeypatch.setenv("KYMFLOW_REMOTE", true_val)
        env = RuntimeEnvironment.detect()
        assert env.native_mode is True, f"Failed for value: {true_val}"
        assert env.is_remote is True, f"Failed for value: {true_val}"
    
    # Test various "false" formats
    for false_val in ["0", "false", "False", "FALSE", "no", "No", "NO", "off", "Off", "OFF"]:
        monkeypatch.setenv("KYMFLOW_GUI_NATIVE", false_val)
        monkeypatch.setenv("KYMFLOW_REMOTE", false_val)
        env = RuntimeEnvironment.detect()
        assert env.native_mode is False, f"Failed for value: {false_val}"
        assert env.is_remote is False, f"Failed for value: {false_val}"


def test_runtime_environment_invalid_env_var_defaults(monkeypatch) -> None:
    """Test RuntimeEnvironment falls back to defaults for invalid env var values."""
    from kymflow.gui_v2.app_context import RuntimeEnvironment
    
    # Invalid values should fall back to defaults
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "invalid")
    monkeypatch.setenv("KYMFLOW_REMOTE", "invalid")
    
    env = RuntimeEnvironment.detect()
    
    # Should use defaults (True for native, False for remote)
    assert env.native_mode is True  # Default
    assert env.is_remote is False  # Default


def test_app_context_initializes_runtime_env_main_process(tmp_path: Path, monkeypatch) -> None:
    """Test that AppContext initializes runtime_env in main process."""
    # Reset singleton
    AppContext._instance = None
    
    # Mock multiprocessing to ensure we're in main process
    class MockProcess:
        name = "MainProcess"
    
    monkeypatch.setattr(app_context, "mp", SimpleNamespace(current_process=lambda: MockProcess()))
    
    # Mock ui
    def create_mock_ui_element():
        return SimpleNamespace(default_classes=lambda x: None, default_props=lambda x: None)
    
    mock_ui = SimpleNamespace(
        label=create_mock_ui_element(),
        button=create_mock_ui_element(),
        checkbox=create_mock_ui_element(),
        select=create_mock_ui_element(),
        input=create_mock_ui_element(),
        number=create_mock_ui_element(),
        expansion=create_mock_ui_element(),
        slider=create_mock_ui_element(),
        linear_progress=create_mock_ui_element(),
        menu=create_mock_ui_element(),
        menu_item=create_mock_ui_element(),
        radio=create_mock_ui_element(),
    )
    
    monkeypatch.setattr(app_context, "ui", mock_ui)
    
    # Set env vars for testing
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "0")
    monkeypatch.setenv("KYMFLOW_REMOTE", "1")
    
    # Initialize AppContext
    context = AppContext()
    
    # Verify runtime_env is initialized
    assert context.runtime_env is not None
    assert context.runtime_env.native_mode is False
    assert context.runtime_env.is_remote is True
    assert context.runtime_env.has_file_system_access is False


def test_app_context_initializes_runtime_env_worker_process(monkeypatch) -> None:
    """Test that AppContext initializes runtime_env in worker process."""
    # Reset singleton
    AppContext._instance = None
    
    # Mock multiprocessing to simulate worker process
    class MockProcess:
        name = "Worker-1"  # Not MainProcess
    
    monkeypatch.setattr(app_context, "mp", SimpleNamespace(current_process=lambda: MockProcess()))
    
    # Set env vars for testing
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "0")
    monkeypatch.setenv("KYMFLOW_REMOTE", "1")
    
    # Initialize AppContext
    context = AppContext()
    
    # Verify runtime_env is initialized even in worker process
    assert context.runtime_env is not None
    assert context.runtime_env.native_mode is False
    assert context.runtime_env.is_remote is True
    assert context.runtime_env.has_file_system_access is False
    
    # Verify other attributes are None in worker process
    assert context.app_config is None
    assert context.app_state is None


def test_runtime_environment_file_system_access_logic(monkeypatch) -> None:
    """Test has_file_system_access logic for all combinations."""
    from kymflow.gui_v2.app_context import RuntimeEnvironment
    
    test_cases = [
        # (native_mode, is_remote, expected_has_file_system_access)
        (True, False, True),   # Local native - has access
        (True, True, True),   # Native even if remote - has access
        (False, False, True), # Local browser - has access
        (False, True, False), # Remote browser - no access
    ]
    
    for native, remote, expected_access in test_cases:
        native_val = "1" if native else "0"
        remote_val = "1" if remote else "0"
        
        monkeypatch.setenv("KYMFLOW_GUI_NATIVE", native_val)
        monkeypatch.setenv("KYMFLOW_REMOTE", remote_val)
        
        env = RuntimeEnvironment.detect()
        
        assert env.native_mode == native, f"Failed for native={native}, remote={remote}"
        assert env.is_remote == remote, f"Failed for native={native}, remote={remote}"
        assert env.has_file_system_access == expected_access, (
            f"Failed for native={native}, remote={remote}: "
            f"expected {expected_access}, got {env.has_file_system_access}"
        )
