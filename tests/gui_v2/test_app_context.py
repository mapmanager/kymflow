"""Tests for AppContext behavior in GUI v2."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from kymflow.core.plotting.theme import ThemeMode
from kymflow.gui_v2 import app_context
from kymflow.gui_v2.app_context import AppContext, THEME_STORAGE_KEY
from kymflow.gui_v2.app_config import AppConfig, DEFAULT_TEXT_SIZE


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
