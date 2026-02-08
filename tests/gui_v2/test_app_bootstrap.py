"""Tests for GUI v2 app startup behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import importlib.util
import sys

import pytest
from nicegui import app, ui

from kymflow.gui_v2.events_folder import SelectPathEvent
from kymflow.core.user_config import UserConfig


class DummyPage:
    """Minimal page stub with render + bus.emit."""

    def __init__(self, bus) -> None:
        self.bus = bus
        self.render_calls: list[str] = []

    def render(self, *, page_title: str) -> None:
        self.render_calls.append(page_title)


def _load_app_module(monkeypatch):
    """Load gui_v2.app without executing its main() import side effect."""
    monkeypatch.setattr(ui, "page", lambda *_args, **_kwargs: (lambda fn: fn))

    import kymflow.gui_v2 as gui_v2_pkg

    app_path = Path(gui_v2_pkg.__file__).with_name("app.py")
    module_name = "kymflow.gui_v2._app_test"
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    app_module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = app_module
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(app_module)

    monkeypatch.setattr(app_module.ui, "page_title", lambda *_: None)
    return app_module


def test_home_reuses_cached_page(monkeypatch) -> None:
    """Home route should reuse cached page when available."""
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(app_module, "inject_global_styles", lambda: None)
    monkeypatch.setattr(app_module, "get_stable_session_id", lambda: "session-1")

    cached_page = DummyPage(bus=SimpleNamespace(emit=MagicMock()))
    monkeypatch.setattr(app_module, "get_cached_page", lambda *_: cached_page)
    monkeypatch.setattr(app_module, "cache_page", lambda *_: None)
    monkeypatch.setattr(app_module, "get_event_bus", lambda *_: object())

    def _fail_homepage(*_args, **_kwargs):
        raise AssertionError("HomePage should not be instantiated when cached")

    monkeypatch.setattr(app_module, "HomePage", _fail_homepage)

    app_module.home()

    assert cached_page.render_calls == ["KymFlow"]


def test_home_bootstrap_emits_folder_chosen(monkeypatch, tmp_path: Path) -> None:
    """Home route should emit SelectPathEvent when last folder exists in config."""
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(app_module, "inject_global_styles", lambda: None)
    monkeypatch.setattr(app_module, "get_stable_session_id", lambda: "session-1")
    monkeypatch.setattr(app_module, "get_cached_page", lambda *_: None)
    monkeypatch.setattr(app_module, "cache_page", lambda *_: None)

    bus = SimpleNamespace(emit=MagicMock())
    monkeypatch.setattr(app_module, "get_event_bus", lambda *_: bus)

    def _homepage(_context, _bus):
        return DummyPage(bus=_bus)

    monkeypatch.setattr(app_module, "HomePage", _homepage)

    # Set up user config with last folder
    app_module.context.app_state.folder = None
    app_module.context.user_config.push_recent_path(str(tmp_path), depth=1)
    app_module.context.user_config.save()

    app_module.home()

    bus.emit.assert_called_once()
    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, SelectPathEvent)
    assert emitted.new_path == str(tmp_path)
    assert emitted.depth == 1  # Depth from config
    assert emitted.phase == "intent"


def test_home_bootstrap_skips_if_folder_loaded(monkeypatch, tmp_path: Path) -> None:
    """Home route should not emit SelectPathEvent if folder already loaded."""
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(app_module, "inject_global_styles", lambda: None)
    monkeypatch.setattr(app_module, "get_stable_session_id", lambda: "session-1")
    monkeypatch.setattr(app_module, "get_cached_page", lambda *_: None)
    monkeypatch.setattr(app_module, "cache_page", lambda *_: None)

    bus = SimpleNamespace(emit=MagicMock())
    monkeypatch.setattr(app_module, "get_event_bus", lambda *_: bus)
    monkeypatch.setattr(app_module, "HomePage", lambda _context, _bus: DummyPage(bus=_bus))

    # Set up user config with last folder
    app_module.context.user_config.push_recent_path(str(tmp_path), depth=1)
    app_module.context.user_config.save()
    
    # But folder is already loaded
    app_module.context.app_state.folder = tmp_path

    app_module.home()

    bus.emit.assert_not_called()


def test_home_bootstrap_loads_last_folder_from_config(monkeypatch, tmp_path: Path) -> None:
    """Home route should load last folder from config."""
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(app_module, "inject_global_styles", lambda: None)
    monkeypatch.setattr(app_module, "get_stable_session_id", lambda: "session-1")
    monkeypatch.setattr(app_module, "get_cached_page", lambda *_: None)
    monkeypatch.setattr(app_module, "cache_page", lambda *_: None)

    bus = SimpleNamespace(emit=MagicMock())
    monkeypatch.setattr(app_module, "get_event_bus", lambda *_: bus)

    def _homepage(_context, _bus):
        return DummyPage(bus=_bus)

    monkeypatch.setattr(app_module, "HomePage", _homepage)

    # Set up user config with last folder
    app_module.context.app_state.folder = None
    app_module.context.user_config.push_recent_path(str(tmp_path), depth=2)
    app_module.context.user_config.save()

    app_module.home()

    bus.emit.assert_called_once()
    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, SelectPathEvent)
    assert emitted.new_path == str(tmp_path)
    assert emitted.depth == 2  # Depth from config
    assert emitted.phase == "intent"




def test_main_registers_shutdown_handlers(monkeypatch) -> None:
    """main() should register shutdown handlers before ui.run()."""
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(app_module, "DEFAULT_PORT", 9999)

    install_mock = MagicMock()
    monkeypatch.setattr(app_module, "install_shutdown_handlers", install_mock)
    monkeypatch.setattr(app_module.ui, "run", lambda **_kwargs: None)

    app_module.main(native=True)

    install_mock.assert_called_once_with(app_module.context, native=True)


def test_home_bootstrap_no_user_config_no_emit(monkeypatch) -> None:
    """Home route should not emit SelectPathEvent when user config has no last folder."""
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(app_module, "inject_global_styles", lambda: None)
    monkeypatch.setattr(app_module, "get_stable_session_id", lambda: "session-1")
    monkeypatch.setattr(app_module, "get_cached_page", lambda *_: None)
    monkeypatch.setattr(app_module, "cache_page", lambda *_: None)

    bus = SimpleNamespace(emit=MagicMock())
    monkeypatch.setattr(app_module, "get_event_bus", lambda *_: bus)

    def _homepage(_context, _bus):
        return DummyPage(bus=_bus)

    monkeypatch.setattr(app_module, "HomePage", _homepage)

    # Set up user config with empty recent_folders and no last_folder
    # (simulating first-time user with no config)
    app_module.context.app_state.folder = None
    # Explicitly reset last_folder to empty (simulating fresh config)
    # Directly set the data to avoid normalization issues with empty string
    from kymflow.core.user_config import LastPath, DEFAULT_FOLDER_DEPTH
    app_module.context.user_config.data.last_path = LastPath(path="", depth=DEFAULT_FOLDER_DEPTH)
    # Verify config has no last folder
    last_path, _ = app_module.context.user_config.get_last_path()
    assert last_path == ""

    app_module.home()

    # Should NOT emit SelectPathEvent since there's no folder to load
    bus.emit.assert_not_called()


def test_home_bootstrap_loads_csv_from_last_path(monkeypatch, tmp_path: Path) -> None:
    """Home route should load CSV from last_path when it's a CSV file."""
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(app_module, "inject_global_styles", lambda: None)
    monkeypatch.setattr(app_module, "get_stable_session_id", lambda: "session-1")
    monkeypatch.setattr(app_module, "get_cached_page", lambda *_: None)
    monkeypatch.setattr(app_module, "cache_page", lambda *_: None)

    bus = SimpleNamespace(emit=MagicMock())
    monkeypatch.setattr(app_module, "get_event_bus", lambda *_: bus)

    def _homepage(_context, _bus):
        return DummyPage(bus=_bus)

    monkeypatch.setattr(app_module, "HomePage", _homepage)

    # Create CSV file
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("path\n/file1.tif\n/file2.tif")
    
    # Set up user config with CSV as last path
    app_module.context.app_state.folder = None
    app_module.context.user_config.push_recent_csv(str(csv_file))
    app_module.context.user_config.save()

    app_module.home()

    # Should emit SelectPathEvent for CSV
    bus.emit.assert_called_once()
    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, SelectPathEvent)
    assert emitted.new_path == str(csv_file)
    # Should NOT have csv_path field (auto-detected by controller)
    assert not hasattr(emitted, 'csv_path') or getattr(emitted, 'csv_path', None) is None
    assert emitted.phase == "intent"
