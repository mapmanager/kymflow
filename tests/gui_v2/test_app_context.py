"""Tests for AppContext behavior in GUI v2."""

from __future__ import annotations

from types import SimpleNamespace

from kymflow.core.plotting.theme import ThemeMode
from kymflow.gui_v2 import app_context
from kymflow.gui_v2.app_context import AppContext, THEME_STORAGE_KEY


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
