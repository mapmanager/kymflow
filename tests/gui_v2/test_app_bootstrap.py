"""Tests for GUI v2 app startup behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import importlib.util
import multiprocessing
import sys

import pytest
from nicegui import app, ui

from kymflow.gui_v2.events_folder import SelectPathEvent
from kymflow.gui_v2.app_context import AppContext
import os
from kymflow.core.user_config import UserConfig


def _fresh_app_context() -> AppContext:
    """Reset singleton and return the AppContext ``home()`` will use."""
    AppContext._instance = None
    return AppContext()


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
    # Disable file logging while importing the app module so tests do not
    # attempt to write to the real user log directory (which may be
    # unwritable in sandboxed environments such as Cursor).
    os.environ["KYMFLOW_DISABLE_FILE_LOG"] = "1"

    # AppContext() runs at import; ensure we are "main" so app_state is initialized.
    class _MainProcess:
        name = "MainProcess"

    monkeypatch.setattr(multiprocessing, "current_process", lambda: _MainProcess())

    AppContext._instance = None

    import kymflow.gui_v2 as gui_v2_pkg

    app_path = Path(gui_v2_pkg.__file__).with_name("app.py")
    module_name = "kymflow.gui_v2._app_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    app_module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = app_module
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(app_module)

    monkeypatch.setattr(app_module.ui, "page_title", lambda *_: None)
    return app_module


def test_home_reuses_cached_page(monkeypatch) -> None:
    """Home route should reuse cached page when available."""
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "0")
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
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "0")
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

    ctx = _fresh_app_context()
    ctx.app_state.folder = None
    ctx.user_config.push_recent_path(str(tmp_path), depth=1)
    ctx.user_config.save()

    app_module.home()

    bus.emit.assert_called_once()
    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, SelectPathEvent)
    assert emitted.new_path == str(tmp_path)
    assert emitted.depth == 1  # Depth from config
    assert emitted.phase == "intent"


def test_home_bootstrap_skips_if_folder_loaded(monkeypatch, tmp_path: Path) -> None:
    """Home route should not emit SelectPathEvent if folder already loaded."""
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "0")
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(app_module, "inject_global_styles", lambda: None)
    monkeypatch.setattr(app_module, "get_stable_session_id", lambda: "session-1")
    monkeypatch.setattr(app_module, "get_cached_page", lambda *_: None)
    monkeypatch.setattr(app_module, "cache_page", lambda *_: None)

    bus = SimpleNamespace(emit=MagicMock())
    monkeypatch.setattr(app_module, "get_event_bus", lambda *_: bus)
    monkeypatch.setattr(app_module, "HomePage", lambda _context, _bus: DummyPage(bus=_bus))

    ctx = _fresh_app_context()
    ctx.user_config.push_recent_path(str(tmp_path), depth=1)
    ctx.user_config.save()
    ctx.app_state.folder = tmp_path

    app_module.home()

    bus.emit.assert_not_called()


def test_home_bootstrap_loads_last_folder_from_config(monkeypatch, tmp_path: Path) -> None:
    """Home route should load last folder from config."""
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "0")
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

    ctx = _fresh_app_context()
    ctx.app_state.folder = None
    ctx.user_config.push_recent_path(str(tmp_path), depth=2)
    ctx.user_config.save()

    app_module.home()

    bus.emit.assert_called_once()
    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, SelectPathEvent)
    assert emitted.new_path == str(tmp_path)
    assert emitted.depth == 2  # Depth from config
    assert emitted.phase == "intent"


def test_main_invokes_ui_run(monkeypatch) -> None:
    """main() calls ui.run; shutdown handlers are no longer registered at module scope."""
    app_module = _load_app_module(monkeypatch)
    run_mock = MagicMock()
    monkeypatch.setattr(app_module.ui, "run", run_mock)
    app_module.main(native_bool=False)
    run_mock.assert_called_once()


def test_home_bootstrap_no_user_config_no_emit(monkeypatch) -> None:
    """Home route should not emit SelectPathEvent when user config has no last folder."""
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "0")
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

    ctx = _fresh_app_context()
    ctx.app_state.folder = None
    from kymflow.core.user_config import LastPath, DEFAULT_FOLDER_DEPTH

    ctx.user_config.data.last_path = LastPath(path="", depth=DEFAULT_FOLDER_DEPTH)
    last_path, _ = ctx.user_config.get_last_path()
    assert last_path == ""

    app_module.home()

    # Should NOT emit SelectPathEvent since there's no folder to load
    bus.emit.assert_not_called()


def test_home_bootstrap_loads_csv_from_last_path(monkeypatch, tmp_path: Path) -> None:
    """Home route should load CSV from last_path when it's a CSV file."""
    monkeypatch.setenv("KYMFLOW_GUI_NATIVE", "0")
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

    csv_file = tmp_path / "test.csv"
    csv_file.write_text("path\n/file1.tif\n/file2.tif")

    ctx = _fresh_app_context()
    ctx.app_state.folder = None
    ctx.user_config.push_recent_csv(str(csv_file))
    ctx.user_config.save()

    app_module.home()

    # Should emit SelectPathEvent for CSV
    bus.emit.assert_called_once()
    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, SelectPathEvent)
    assert emitted.new_path == str(csv_file)
    # Should NOT have csv_path field (auto-detected by controller)
    assert not hasattr(emitted, 'csv_path') or getattr(emitted, 'csv_path', None) is None
    assert emitted.phase == "intent"
