"""Tests for GUI v2 app startup behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import importlib.util
import sys

import pytest
from nicegui import app, ui

from kymflow.gui_v2.events_folder import FolderChosen
from kymflow.gui_v2.shutdown_handlers import _capture_native_window_rect
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
    """Home route should emit FolderChosen once when dev folder exists."""
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

    monkeypatch.setattr(app_module, "USE_DEV_FOLDER", True)
    monkeypatch.setattr(app_module, "DEV_FOLDER", tmp_path)

    app_module.context.app_state.folder = None

    app_module.home()

    bus.emit.assert_called_once()
    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, FolderChosen)
    assert emitted.folder == str(tmp_path)
    assert emitted.depth is None  # Dev folder doesn't specify depth


def test_home_bootstrap_skips_if_folder_loaded(monkeypatch, tmp_path: Path) -> None:
    """Home route should not emit FolderChosen if folder already loaded."""
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(app_module, "inject_global_styles", lambda: None)
    monkeypatch.setattr(app_module, "get_stable_session_id", lambda: "session-1")
    monkeypatch.setattr(app_module, "get_cached_page", lambda *_: None)
    monkeypatch.setattr(app_module, "cache_page", lambda *_: None)

    bus = SimpleNamespace(emit=MagicMock())
    monkeypatch.setattr(app_module, "get_event_bus", lambda *_: bus)
    monkeypatch.setattr(app_module, "HomePage", lambda _context, _bus: DummyPage(bus=_bus))

    monkeypatch.setattr(app_module, "USE_DEV_FOLDER", True)
    monkeypatch.setattr(app_module, "DEV_FOLDER", tmp_path)

    app_module.context.app_state.folder = tmp_path

    app_module.home()

    bus.emit.assert_not_called()


def test_home_bootstrap_loads_last_folder_from_config(monkeypatch, tmp_path: Path) -> None:
    """Home route should load last folder from config when dev override is disabled."""
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

    # Disable dev folder override
    monkeypatch.setattr(app_module, "USE_DEV_FOLDER", False)
    
    # Set up user config with last folder
    app_module.context.app_state.folder = None
    app_module.context.user_config.push_recent_folder(str(tmp_path), depth=2)
    app_module.context.user_config.save()

    app_module.home()

    bus.emit.assert_called_once()
    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, FolderChosen)
    assert emitted.folder == str(tmp_path)
    assert emitted.depth == 2  # Depth from config


def test_home_bootstrap_dev_override_takes_precedence(monkeypatch, tmp_path: Path) -> None:
    """Home route should prefer dev folder over last folder from config."""
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

    # Enable dev folder override
    dev_folder = tmp_path / "dev"
    dev_folder.mkdir()
    monkeypatch.setattr(app_module, "USE_DEV_FOLDER", True)
    monkeypatch.setattr(app_module, "DEV_FOLDER", dev_folder)
    
    # Set up user config with different last folder
    config_folder = tmp_path / "config"
    config_folder.mkdir()
    app_module.context.app_state.folder = None
    app_module.context.user_config.push_recent_folder(str(config_folder), depth=3)
    app_module.context.user_config.save()

    app_module.home()

    # Should emit dev folder, not config folder
    bus.emit.assert_called_once()
    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, FolderChosen)
    assert emitted.folder == str(dev_folder)
    assert emitted.depth is None  # Dev folder doesn't specify depth


def test_main_registers_shutdown_handlers(monkeypatch) -> None:
    """main() should register shutdown handlers before ui.run()."""
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(app_module, "_warm_mpl_font_cache_once", lambda: None)
    monkeypatch.setattr(app_module, "DEFAULT_PORT", 9999)

    install_mock = MagicMock()
    monkeypatch.setattr(app_module, "install_shutdown_handlers", install_mock)
    monkeypatch.setattr(app_module.ui, "run", lambda **_kwargs: None)

    app_module.main(native=True)

    install_mock.assert_called_once_with(app_module.context, native=True)


@pytest.mark.asyncio
async def test_shutdown_captures_native_window_rect(monkeypatch, tmp_path: Path) -> None:
    """Ensure native window rect is captured on shutdown."""
    cfg_path = tmp_path / "user_config.json"
    cfg = UserConfig.load(config_path=cfg_path)
    context = SimpleNamespace(user_config=cfg)

    class DummyWindow:
        async def get_size(self):
            return (1200, 800)

        async def get_position(self):
            return (10, 20)

    monkeypatch.setattr(app.native, "main_window", DummyWindow())

    await _capture_native_window_rect(context)

    assert cfg.get_window_rect() == (10, 20, 1200, 800)
