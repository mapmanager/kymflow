"""Tests for page cache utilities."""

from __future__ import annotations

from types import SimpleNamespace

from kymflow.gui_v2 import page_cache


class DummyStorage:
    """Simple storage stub mimicking nicegui.app.storage."""

    def __init__(self) -> None:
        self.user: dict[str, str] = {}


def test_get_stable_session_id_persists(monkeypatch) -> None:
    """Stable session ID should persist in storage across calls."""
    storage = DummyStorage()
    monkeypatch.setattr(page_cache, "app", SimpleNamespace(storage=storage))

    session_id_1 = page_cache.get_stable_session_id()
    session_id_2 = page_cache.get_stable_session_id()

    assert session_id_1 == session_id_2
    assert storage.user["_kymflow_v2_session_id"] == session_id_1


def test_cache_page_roundtrip() -> None:
    """Cache and fetch a page instance by session and route."""
    page_cache._PAGE_CACHE.clear()
    dummy_page = object()
    session_id = "session-1"
    route = "/"

    page_cache.cache_page(session_id, route, dummy_page)

    assert page_cache.get_cached_page(session_id, route) is dummy_page


def test_clear_session_pages() -> None:
    """Clearing a session should remove only that session's cached pages."""
    page_cache._PAGE_CACHE.clear()
    page_cache.cache_page("session-1", "/", object())
    page_cache.cache_page("session-1", "/test", object())
    page_cache.cache_page("session-2", "/", object())

    page_cache.clear_session_pages("session-1")

    assert page_cache.get_cached_page("session-1", "/") is None
    assert page_cache.get_cached_page("session-1", "/test") is None
    assert page_cache.get_cached_page("session-2", "/") is not None
